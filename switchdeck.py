#!/usr/bin/env python3
"""SwitchBar (switchdeck v1.8): menu bar account switcher + usage deck.

Wraps cswap (claude-swap) to switch between two same-email Claude Code
accounts and shows per-account 5h/7d usage. Owns only the surface; the
engine is an upgradable dependency validated against a pinned contract.

v1.6: live-session awareness. A running Claude Code CLI caches its OAuth
credential in memory (macOS Keychain cache is ~30s), so a switch does not
apply to an already-running session instantly, and never mid-reply. When a
switch succeeds while CLI sessions are live, the notification now says so,
and the click log records the live session count for later audit.

v1.7: engine contract (claude-swap version and JSON schemaVersion pinned,
one warning row on drift, lastGoodUsage fallback with staleness), and the
Codex row made opt-in so a stock install makes zero network calls.

v1.8: auto-switch narration, dry-run only. Each refresh tick additionally
runs one engine auto evaluation (`cswap auto --once --dry-run --json`) and
narrates the outcome: a would-switch raises one notification (deduped per
condition) and a click-log line; errors and blocked outcomes get a click-log
line and one silent menu row. The engine owns thresholds, cooldown, and
strategy; this app never switches and configures none of them.

v1.9: notifications made real, and the resume card. The 2026-08-17 audit
left one item UNVERIFIED: whether a rumps notification renders on macOS
Tahoe 26 from this unbundled Python app. Tested 2026-08-24 on 26.6.2: it
does NOT. rumps resolves its notification centre through an Info.plist
beside the running interpreter, and a venv has none, so every notification
this app has ever fired raised RuntimeError into the swallow at _notify and
nothing drew. Fixed without bundling: the app writes that one-key
Info.plist next to sys.executable at startup (idempotent, survives a venv
rebuild), falls back to osascript when the centre is still unavailable, and
records every notification failure in the click log instead of hiding it.
A silent notification path is now impossible to have without evidence.
With delivery proven, the audit's resume card ships: a switch notification
names the target slot, the verified active org, live CLI session count, and
the project you were last working in, degrading to the previous text on any
parse failure.
"""
import datetime as _dt
import json
import os
import plistlib
import subprocess
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rumps

HOME = os.path.expanduser("~")

# Defaults. Override in gitignored local_settings.py; real labels stay local.
CSWAP_BIN = os.path.join(HOME, ".local", "bin", "cswap")
SLOT_LABELS = {1: "primary", 2: "secondary"}
SHORT_LABELS = {1: "1", 2: "2"}
CLICK_LOG = os.path.join(HOME, "switchdeck-clicks.log")
CLAUDE_JSON = os.path.join(HOME, ".claude.json")
CLAUDE_SESSIONS_DIR = os.path.join(HOME, ".claude", "sessions")
REFRESH_SECONDS = 300
CODEX_REFRESH_SECONDS = 1800

# Notification identity. APP_NAME is the one name this product answers to,
# in the process list, the notification banner, and the app bundle.
# BUNDLE_ID is the bundle's identity; macOS keys notification permission to
# it, so changing it resets the user's notification choices for this app.
# Changed once, deliberately, 2026-08-24: com.shashank.switchdeck carried a
# stale system-level notification DENIAL (authorizationStatus=1 with no way
# to re-prompt), so the identity moved to the com.shashankkarpal.* namespace
# the rest of the fleet uses, which starts notDetermined and prompts.
APP_NAME = "SwitchDeck"
BUNDLE_ID = "com.shashankkarpal.switchdeck"
# Sound for the osascript fallback path. rumps' own notifications carry the
# system default alert sound; this only applies when rumps is unavailable.
# None means the fallback is silent.
NOTIFY_FALLBACK_SOUND = "Ping"
# Codex row is opt-in: None means the row is never built, its timer never
# starts, and a stock install makes zero network calls (the local-only
# guarantee). Enable in local_settings.py, e.g.
# CODEX_USAGE_CMD = ["npx", "-y", "ccusage@latest", "codex", "--json"]
CODEX_USAGE_CMD = None
# Clicking the Codex row jumps into the tool: opens a terminal running codex.
CODEX_LAUNCH_CMD = ["open", "-na", "Ghostty", "--args", "-e", "codex"]
# Dry-run auto-switch narration (v1.8). True narrates what the engine's auto
# mode would do each tick; nothing is ever switched. The only knob here is
# off/on: thresholds, cooldown, and strategy are engine config, not ours.
AUTO_NARRATE = True

# Engine contract: the cswap release and JSON schemaVersion this build is
# validated against (CLAUDE.md decision log). Drift shows a warning row and
# nothing else changes; there is no auto-upgrade. Not overridable locally.
VALIDATED_ENGINE = "0.25.0"
VALIDATED_SCHEMA_VERSION = 1

try:
    import local_settings as _ls
    for _k in ("CSWAP_BIN", "SLOT_LABELS", "SHORT_LABELS", "CLICK_LOG",
               "REFRESH_SECONDS", "CODEX_REFRESH_SECONDS", "CODEX_USAGE_CMD",
               "CODEX_LAUNCH_CMD", "AUTO_NARRATE", "NOTIFY_FALLBACK_SOUND"):
        if hasattr(_ls, _k):
            globals()[_k] = getattr(_ls, _k)
except ImportError:
    pass


def _lbl(d, n, default):
    if not isinstance(d, dict):
        return default
    return d.get(n, d.get(str(n), default))


def _child_env():
    """Environment for subprocesses, without our interpreter's variables.

    When this app runs from the .app bundle, PYTHONHOME and PYTHONPATH wire
    the bundled interpreter to its stdlib and site-packages. Inherited by a
    child Python such as cswap's own venv interpreter, those same variables
    override the child's environment and break its imports. Scrub them for
    every child; non-Python children ignore them anyway.
    """
    env = dict(os.environ)
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    return env


def _run(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, env=_child_env())
        return p.returncode, p.stdout, p.stderr
    except Exception as e:  # noqa: BLE001 - surface anything to the UI
        return 1, "", str(e)


def ensure_notification_bundle():
    """Give rumps an Info.plist to find, next to the running interpreter.

    rumps resolves NSUserNotificationCenter through the Info.plist beside
    sys.executable and needs CFBundleIdentifier in it. A venv has no such
    file, so notifications raise RuntimeError and, before v1.9, vanished
    into the swallow below. Writing the two keys is the whole fix short of
    shipping a real .app bundle, which the 2026-08-17 audit deferred to the
    Swift rewrite.

    Idempotent, and deliberately re-run at every startup: the file lives in
    the venv, not the repo, so a venv rebuild silently removes it. Returns
    (ok, detail) for the click log; never raises.
    """
    try:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        # Inside a real .app bundle (the shipped configuration since v1.9.1)
        # the identity comes from Contents/Info.plist and the bundle is
        # code-signed; writing anything into Contents/MacOS would break the
        # signature. Detect and leave it alone.
        bundle_plist = os.path.join(os.path.dirname(exe_dir), "Info.plist")
        if os.path.basename(exe_dir) == "MacOS" and os.path.exists(bundle_plist):
            try:
                with open(bundle_plist, "rb") as f:
                    bid = plistlib.load(f).get("CFBundleIdentifier")
            except Exception:  # noqa: BLE001
                bid = None
            return True, "bundled (%s)" % (bid or "unreadable Info.plist")
        path = os.path.join(exe_dir, "Info.plist")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    have = plistlib.load(f).get("CFBundleIdentifier")
            except Exception:  # noqa: BLE001 - unreadable counts as absent
                have = None
            if have:
                return True, "present (%s)" % have
        with open(path, "wb") as f:
            plistlib.dump({"CFBundleIdentifier": BUNDLE_ID,
                           "CFBundleName": APP_NAME}, f)
        return True, "written %s" % path
    except Exception as e:  # noqa: BLE001 - never block startup on this
        return False, "%s: %s" % (type(e).__name__, e)


def _notify_fallback(title, subtitle, message):
    """Post a banner without rumps, for when the notification centre is
    unavailable to this process. Shows under whichever app owns osascript
    rather than under our own identity, which is the cost of not bundling;
    it is still better than silence. Text is passed as osascript variables,
    never interpolated into the source, so quotes in an engine error
    message cannot break or inject into the script."""
    script = ('on run argv\n'
              '  display notification (item 3 of argv) '
              'with title (item 1 of argv) subtitle (item 2 of argv)')
    if NOTIFY_FALLBACK_SOUND:
        script += ' sound name (item 4 of argv)'
    script += '\nend run'
    args = ["/usr/bin/osascript", "-e", script,
            str(title), str(subtitle), str(message)]
    if NOTIFY_FALLBACK_SOUND:
        args.append(str(NOTIFY_FALLBACK_SOUND))
    rc, _out, err = _run(args, timeout=10)
    return rc == 0, (err or "").strip()[:120]


def request_notify_authorization():
    """Ask the modern notification centre for banner and sound rights.

    Runs once at startup, from the .app bundle. First launch under a fresh
    identity raises the standard macOS prompt; the user's answer is keyed to
    BUNDLE_ID and remembered. The outcome always lands in the click log,
    including a denial, because a denied identity looks exactly like broken
    code unless something says otherwise (that is how the 2026-08-24 stale
    denial hid). Returns nothing; never raises."""
    try:
        import UserNotifications as UN
        center = UN.UNUserNotificationCenter.currentNotificationCenter()

        def _cb(granted, error):
            log_click("notify authorization granted=%s%s"
                      % (granted, " error=%s" % error if error else ""))
            if not granted:
                log_click("notify DENIED for %s: enable it in System "
                          "Settings > Notifications > %s"
                          % (BUNDLE_ID, APP_NAME))

        opts = UN.UNAuthorizationOptionAlert | UN.UNAuthorizationOptionSound
        center.requestAuthorizationWithOptions_completionHandler_(opts, _cb)
    except Exception as e:  # noqa: BLE001 - never block startup
        log_click("notify authorization request failed: %s: %s"
                  % (type(e).__name__, str(e).splitlines()[0][:100]))


def _notify_modern(title, subtitle, message):
    """Post via UserNotifications (banner plus default sound). Requires the
    .app bundle and granted authorization. Raises on any setup failure so
    the caller can fall back; posting errors are reported asynchronously by
    the centre into the click log."""
    import UserNotifications as UN
    content = UN.UNMutableNotificationContent.alloc().init()
    content.setTitle_(str(title))
    if subtitle:
        content.setSubtitle_(str(subtitle))
    content.setBody_(str(message))
    content.setSound_(UN.UNNotificationSound.defaultSound())
    req = UN.UNNotificationRequest.requestWithIdentifier_content_trigger_(
        "switchdeck-%f" % _dt.datetime.now().timestamp(), content, None)

    def _cb(error):
        if error:
            log_click("notify post error: %s" % error)

    center = UN.UNUserNotificationCenter.currentNotificationCenter()
    center.addNotificationRequest_withCompletionHandler_(req, _cb)


def _notify(title, subtitle, message):
    """Notify: modern centre first, legacy rumps second, osascript last,
    and evidence in the click log for every fallback.

    Notifications stay best-effort (a revoked permission must never crash
    the bar) but they are never silent on failure: a swallowed exception
    here is exactly what hid a year of undelivered notifications, and a
    legacy-only path is exactly what filed banners into Notification Center
    without ever presenting one (found 2026-08-24: NSUserNotification on
    Tahoe stores but does not present for identities without modern
    authorization)."""
    try:
        _notify_modern(title, subtitle, message)
        return
    except Exception as e:  # noqa: BLE001 - any failure falls through
        modern = "%s: %s" % (type(e).__name__, str(e).splitlines()[0][:80])
    try:
        rumps.notification(title, subtitle, message)
        log_click("notify via legacy centre (modern failed: %s)" % modern)
        return
    except Exception as e:  # noqa: BLE001 - any failure falls through
        legacy = "%s: %s" % (type(e).__name__, str(e).splitlines()[0][:80])
    ok, detail = _notify_fallback(title, subtitle, message)
    log_click("notify %s via osascript (modern: %s; legacy: %s)%s"
              % ("ok" if ok else "FAILED", modern, legacy,
                 "" if ok else " fallback: %s" % detail))


def _pid_alive(pid):
    """True if a process with this PID is running (same check cswap uses)."""
    if not isinstance(pid, int) or pid <= 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True  # exists, just not ours
    except OSError:
        return False


def live_claude_sessions():
    """Running Claude Code sessions from ~/.claude/sessions/{pid}.json.

    Claude Code writes one JSON per session and removes it on exit; stale
    files (dead PIDs) are filtered out. This is the same mechanism cswap's
    own process detection uses.
    """
    sessions = []
    try:
        names = os.listdir(CLAUDE_SESSIONS_DIR)
    except OSError:
        return sessions
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(CLAUDE_SESSIONS_DIR, name)) as f:
                data = json.load(f)
            if _pid_alive(data.get("pid")):
                sessions.append(data)
        except (ValueError, TypeError, OSError):
            continue
    return sessions


def cswap_list():
    rc, out, _err = _run([CSWAP_BIN, "list", "--json"])
    if rc != 0 or not out.strip():
        return None
    try:
        data = json.loads(out)
    except ValueError:
        return None
    if "error" in data:
        return None
    return data


def cswap_auto_dryrun():
    """One dry-run tick of the engine's auto-switch. Emits one JSON event
    per line (observed on 0.25.0: a `poll` snapshot, then a terminal
    `switch` or `no-switch`); exit codes with --once are 0 switched,
    1 error, 2 nothing to do, 3 blocked. --dry-run is hard-coded: the
    engine evaluates and reports but never switches or writes state."""
    rc, out, _err = _run([CSWAP_BIN, "auto", "--once", "--dry-run", "--json"])
    events = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    return rc, events


def driving_window(poll, slot_no):
    """(window name, pct) that pushed a slot over the auto threshold, from
    the poll event's windowsPct; the switch event itself does not carry it.
    Falls back to the slot's highest window, or (None, None)."""
    if not isinstance(poll, dict):
        return None, None
    wins = poll.get("windowsPct")
    w = _lbl(wins, slot_no, None) if slot_no is not None else None
    if not isinstance(w, dict):
        return None, None
    cands = {k: v for k, v in w.items() if isinstance(v, (int, float))}
    if not cands:
        return None, None
    thr = poll.get("threshold")
    if isinstance(thr, (int, float)):
        over = {k: v for k, v in cands.items() if v >= thr}
        if over:
            cands = over
    name = max(cands, key=cands.get)
    return name, cands[name]


_ENGINE_VERSION = None


def engine_version():
    """Engine version, resolved once per process. The engine cannot change
    version without a reinstall, and spawning an interpreter on every
    refresh tick was the second-largest cost of the refresh (audit
    2026-09-02). A failed probe is retried on the next call."""
    global _ENGINE_VERSION
    if _ENGINE_VERSION is None:
        rc, out, _err = _run([CSWAP_BIN, "--version"], timeout=10)
        if rc == 0 and out.strip():
            _ENGINE_VERSION = out.strip().split()[-1]
    return _ENGINE_VERSION


def engine_warning(data):
    """One warning line when the engine drifts from the validated contract,
    None when it matches. A missing engine is handled by the retry row, not
    here."""
    ver = engine_version()
    if ver is not None and ver != VALIDATED_ENGINE:
        return "engine %s unvalidated (validated: %s)" % (ver, VALIDATED_ENGINE)
    if isinstance(data, dict) and data.get("schemaVersion") != VALIDATED_SCHEMA_VERSION:
        return "engine schema %s unvalidated (validated: %s)" % (
            data.get("schemaVersion"), VALIDATED_SCHEMA_VERSION)
    return None


def active_org():
    try:
        with open(CLAUDE_JSON) as f:
            a = json.load(f).get("oauthAccount", {})
        return a.get("organizationName", "?"), (a.get("organizationUuid") or "?")[:8]
    except Exception:
        return "?", "?"


def last_project():
    """Basename of the project directory with the most recent Claude Code
    start time, for the resume card.

    Reads only ~/.claude.json, which this app already opens for the active
    org, and returns None on anything unexpected: the notification loses
    one clause, nothing else. Claude Code writes lastStartTime as epoch
    milliseconds (verified 2026-08-24, 11 of 17 projects carry it), but the
    type is not contractual, so the comparison coerces and skips whatever
    will not coerce. HOME is excluded: "shashank.kk" names no project and
    reads as a bug in a banner.
    """
    try:
        with open(CLAUDE_JSON) as f:
            projects = json.load(f).get("projects")
        if not isinstance(projects, dict):
            return None
        best, best_at = None, None
        for path, meta in projects.items():
            if not isinstance(meta, dict) or not isinstance(path, str):
                continue
            if os.path.normpath(path) == os.path.normpath(HOME):
                continue
            try:
                at = float(meta.get("lastStartTime"))
            except (TypeError, ValueError):
                continue
            if best_at is None or at > best_at:
                best, best_at = path, at
        if not best:
            return None
        return os.path.basename(best.rstrip("/")) or best
    except Exception:  # noqa: BLE001 - cosmetic data, never fatal
        return None


def log_click(text):
    """Append one line to the click log, created 0600. The log carries org
    names and project basenames, an activity trail no other local user or
    process needs to read (audit 2026-09-02)."""
    try:
        fd = os.open(CLICK_LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write("%s %s\n" % (_dt.datetime.now().isoformat(timespec="seconds"), text))
    except OSError:
        pass


USAGE_WINDOWS = (("fiveHour", "5h"), ("sevenDay", "7d"), ("spend", "spend"))


def fmt_usage(u):
    """Known windows first in a fixed order (5h, 7d, spend), then anything
    the engine adds later under its raw key, so the row never reorders
    between ticks and a spend_limit window gets a readable label."""
    if not isinstance(u, dict):
        return "usage n/a"
    parts = []
    seen = set()
    for key, label in USAGE_WINDOWS:
        win = u.get(key)
        seen.add(key)
        if isinstance(win, dict) and win.get("pct") is not None:
            parts.append("%s %d%%" % (label, round(win["pct"])))
    for key, win in u.items():
        if key in seen:
            continue
        if isinstance(win, dict) and win.get("pct") is not None:
            parts.append("%s %d%%" % (key, round(win["pct"])))
    return " - ".join(parts) if parts else "usage n/a"


def usage_line(acc):
    """Inline usage for one slot. cswap 0.25.x sets usage to null when the
    live fetch fails and parks the last success in lastGoodUsage, with
    usageStatus and lastGoodAgeSeconds explaining the failure."""
    u = acc.get("usage")
    if isinstance(u, dict):
        return fmt_usage(u)
    lg = acc.get("lastGoodUsage")
    if not isinstance(lg, dict):
        return "usage n/a"
    try:
        days = int(float(acc.get("lastGoodAgeSeconds")) // 86400)
        stale = "stale %dd" % days if days >= 1 else "stale <1d"
    except (TypeError, ValueError):
        stale = "stale"
    status = acc.get("usageStatus")
    if status and status != "ok":
        stale = "%s, %s" % (stale, str(status).replace("_", " "))
    return "%s (%s)" % (fmt_usage(lg), stale)


def summarize_codex(d):
    t = d.get("totals") or d.get("total") or {}
    cost = t.get("totalCost", t.get("costUSD", t.get("cost")))
    toks = t.get("totalTokens", t.get("tokens"))
    bits = []
    if cost is not None:
        try:
            bits.append("$%.2f" % float(cost))
        except (TypeError, ValueError):
            pass
    if toks is not None:
        try:
            bits.append("%dk tok" % (int(toks) // 1000))
        except (TypeError, ValueError):
            pass
    return " - ".join(bits) if bits else "connected"


class SwitchDeck(rumps.App):
    def __init__(self):
        super(SwitchDeck, self).__init__("=", quit_button=None)
        self.codex_line = "Codex: not configured"
        # Last notified would-switch condition: (from, to, driving window).
        # In-memory only; a restart may re-notify once, accepted over
        # persistence. Cleared on no-switch so a returning condition
        # (window reset, then filled again) notifies again.
        self._auto_key = None
        self.refresh_timer = rumps.Timer(self.refresh, REFRESH_SECONDS)
        self.refresh_timer.start()
        if CODEX_USAGE_CMD:
            self.codex_line = "Codex: loading..."
            self.codex_timer = rumps.Timer(self.refresh_codex, CODEX_REFRESH_SECONDS)
            self.codex_timer.start()
            self.refresh_codex(None)
        self.refresh(None)

    # ---- Claude accounts ----
    def refresh_all(self, _sender=None):
        """Manual Refresh only. The 300s timer and retry row call refresh()
        directly; keeping Codex off that path is what holds the local-only
        guarantee (a rumps Timer passes itself as sender, so sender
        truthiness cannot distinguish a tick from a click)."""
        self.refresh_codex()
        self.refresh()

    def refresh(self, _sender=None):
        data = cswap_list()
        items = []
        active_no = None
        if data and isinstance(data.get("accounts"), list):
            active_no = data.get("activeAccountNumber")
            for acc in sorted(data["accounts"], key=lambda a: a.get("number", 0)):
                n = acc.get("number")
                label = _lbl(SLOT_LABELS, n, "slot %s" % n)
                mark = u"✓ " if acc.get("active") else "     "
                title = "%s%s  -  %s" % (mark, label, usage_line(acc))
                cb = None if acc.get("active") else self._make_switch(n, label)
                items.append(rumps.MenuItem(title, callback=cb))
        else:
            items.append(rumps.MenuItem("cswap unavailable - click to retry",
                                        callback=self.refresh))
        warn = engine_warning(data)
        if warn:
            items.append(rumps.MenuItem(warn, callback=None))
        if AUTO_NARRATE:
            auto_row = self._narrate_auto()
            if auto_row:
                items.append(rumps.MenuItem(auto_row, callback=None))
        org, _u8 = active_org()
        self.title = u"⇄ %s" % _lbl(SHORT_LABELS, active_no, "?")
        items.append(rumps.separator)
        if CODEX_USAGE_CMD:
            items.append(rumps.MenuItem(self.codex_line + "  -  click to open",
                                        callback=self._open_codex))
        items.append(rumps.MenuItem("Active org: %s" % org, callback=None))
        live = live_claude_sessions()
        if live:
            items.append(rumps.MenuItem(
                "%d live CLI session(s): switch applies in ~30s, not mid-reply"
                % len(live), callback=None))
        items.append(rumps.separator)
        items.append(rumps.MenuItem("Refresh", callback=self.refresh_all))
        items.append(rumps.MenuItem("Quit", callback=self._quit))
        self.menu.clear()
        for it in items:
            self.menu.add(it)

    def _narrate_auto(self):
        """Narrate one engine auto dry-run tick. A would-switch notifies
        once per distinct condition and always logs; poll and no-switch are
        silent; error and blocked outcomes log and return one non-clickable
        menu row string (never a notification). Returns None otherwise."""
        rc, events = cswap_auto_dryrun()
        poll = next((e for e in events if e.get("event") == "poll"), None)
        final = next((e for e in reversed(events)
                      if e.get("event") != "poll"), None)
        kind = (final or {}).get("event")
        if kind == "switch":
            from_no = (final.get("from") or {}).get("number")
            to_no = (final.get("to") or {}).get("number")
            win, pct = driving_window(poll, from_no)
            detail = ("%s at %d%%" % (win, round(pct)) if win
                      else "threshold reached")
            key = (from_no, to_no, win)
            deduped = key == self._auto_key
            log_click("auto-dryrun would-switch %s->%s %s%s"
                      % (from_no, to_no, detail,
                         " (deduped)" if deduped else ""))
            if not deduped:
                self._auto_key = key
                _notify(APP_NAME, "Auto (dry-run)",
                        "Would switch slot %s to slot %s, %s. "
                        "No switch performed." % (from_no, to_no, detail))
            return None
        if kind == "no-switch" or rc == 2:
            self._auto_key = None
            return None
        label = "blocked" if rc == 3 or kind == "blocked" else "error"
        reason = ""
        if isinstance(final, dict):
            reason = str(final.get("reason") or final.get("detail")
                         or final.get("error") or "").strip()
        log_click("auto-dryrun %s rc=%s %s"
                  % (label, rc, reason or kind or "no event"))
        return ("auto dry-run %s: %s"
                % (label, reason or "see click log"))[:80]

    def _make_switch(self, n, label):
        def _cb(_sender):
            rc, out, err = _run([CSWAP_BIN, "switch", str(n), "--json"])
            ok = rc == 0
            try:
                ok = bool(json.loads(out).get("switched", ok))
            except ValueError:
                pass
            if ok:
                live = live_claude_sessions()
                proj = last_project()
                log_click("menubar switch-to %s (%s) live_cli=%d project=%s"
                          % (n, label, len(live), proj or "-"))
                org, u8 = active_org()
                # Resume card: what you need to carry on, in one banner.
                # Org is the proof the switch landed; the live-session line
                # is the one thing that changes what you do next, so it
                # stays first when it applies.
                if live:
                    body = ("%d live CLI session(s): applies in ~30s, "
                            "not mid-reply." % len(live))
                else:
                    body = "Active org: %s (%s...)" % (org, u8)
                if proj:
                    body = "%s Last project: %s." % (body, proj)
                _notify(APP_NAME, "Switched to %s" % label, body)
            else:
                _notify(APP_NAME, "Switch failed",
                        (err or out or "unknown error").strip()[:120])
            self.refresh(None)
        return _cb

    # ---- Codex (read-only usage; single account, nothing to switch) ----
    def refresh_codex(self, _sender=None):
        threading.Thread(target=self._codex_worker, daemon=True).start()

    def _codex_worker(self):
        if not CODEX_USAGE_CMD:
            self.codex_line = "Codex: not configured"
            return
        rc, out, _err = _run(CODEX_USAGE_CMD, timeout=90)
        line = "Codex: n/a"
        if rc == 0 and out.strip():
            try:
                line = "Codex: " + summarize_codex(json.loads(out))
            except ValueError:
                line = "Codex: unparsed output"
        self.codex_line = line

    def _open_codex(self, _sender):
        """Tool jump: Claude and Codex credentials coexist, so 'switching' to
        Codex means launching it. Account-level Codex switching needs a second
        Codex account and stays gated (see ROADMAP)."""
        log_click("menubar open codex")
        rc, _out, err = _run(CODEX_LAUNCH_CMD, timeout=15)
        if rc == 0:
            _notify(APP_NAME, "Codex", "Opening Codex")
        else:
            _notify(APP_NAME, "Codex launch failed", (err or "check CODEX_LAUNCH_CMD")[:120])

    def _quit(self, _sender):
        log_click("menubar quit")
        rumps.quit_application()


if __name__ == "__main__":
    _ok, _detail = ensure_notification_bundle()
    log_click("start %s notification-bundle %s: %s"
              % (APP_NAME, "ok" if _ok else "FAILED", _detail))
    request_notify_authorization()
    SwitchDeck().run()
