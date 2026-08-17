#!/usr/bin/env python3
"""SwitchBar (switchdeck v1.6): menu bar account switcher + usage deck.

Wraps cswap (claude-swap) to switch between two same-email Claude Code
accounts, shows per-account 5h/7d usage, and a read-only Codex usage row.
Owns only the surface; the engine is an upgradable dependency.

v1.6: live-session awareness. A running Claude Code CLI caches its OAuth
credential in memory (macOS Keychain cache is ~30s), so a switch does not
apply to an already-running session instantly, and never mid-reply. When a
switch succeeds while CLI sessions are live, the notification now says so,
and the click log records the live session count for later audit.
"""
import datetime as _dt
import json
import os
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
CODEX_USAGE_CMD = ["npx", "-y", "ccusage@latest", "codex", "--json"]
# Clicking the Codex row jumps into the tool: opens a terminal running codex.
CODEX_LAUNCH_CMD = ["open", "-na", "Ghostty", "--args", "-e", "codex"]

# Engine contract: the cswap release and JSON schemaVersion this build is
# validated against (CLAUDE.md decision log). Drift shows a warning row and
# nothing else changes; there is no auto-upgrade. Not overridable locally.
VALIDATED_ENGINE = "0.25.0"
VALIDATED_SCHEMA_VERSION = 1

try:
    import local_settings as _ls
    for _k in ("CSWAP_BIN", "SLOT_LABELS", "SHORT_LABELS", "CLICK_LOG",
               "REFRESH_SECONDS", "CODEX_REFRESH_SECONDS", "CODEX_USAGE_CMD",
               "CODEX_LAUNCH_CMD"):
        if hasattr(_ls, _k):
            globals()[_k] = getattr(_ls, _k)
except ImportError:
    pass


def _lbl(d, n, default):
    if not isinstance(d, dict):
        return default
    return d.get(n, d.get(str(n), default))


def _run(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:  # noqa: BLE001 - surface anything to the UI
        return 1, "", str(e)


def _notify(title, subtitle, message):
    try:
        rumps.notification(title, subtitle, message)
    except Exception:
        pass  # notifications are best-effort; never crash the bar


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


def engine_version():
    rc, out, _err = _run([CSWAP_BIN, "--version"], timeout=10)
    if rc != 0 or not out.strip():
        return None
    return out.strip().split()[-1]


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


def log_click(text):
    try:
        with open(CLICK_LOG, "a") as f:
            f.write("%s %s\n" % (_dt.datetime.now().isoformat(timespec="seconds"), text))
    except OSError:
        pass


def fmt_usage(u):
    if not isinstance(u, dict):
        return "usage n/a"
    label_map = {"fiveHour": "5h", "sevenDay": "7d"}
    parts = []
    for key, win in u.items():
        if isinstance(win, dict) and win.get("pct") is not None:
            parts.append("%s %d%%" % (label_map.get(key, key), round(win["pct"])))
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


class SwitchBar(rumps.App):
    def __init__(self):
        super(SwitchBar, self).__init__("=", quit_button=None)
        self.codex_line = "Codex: loading..."
        self.refresh_timer = rumps.Timer(self.refresh, REFRESH_SECONDS)
        self.codex_timer = rumps.Timer(self.refresh_codex, CODEX_REFRESH_SECONDS)
        self.refresh_timer.start()
        self.codex_timer.start()
        self.refresh_codex(None)
        self.refresh(None)

    # ---- Claude accounts ----
    def refresh(self, _sender=None):
        if _sender is not None:
            self.refresh_codex()
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
        org, _u8 = active_org()
        self.title = u"⇄ %s" % _lbl(SHORT_LABELS, active_no, "?")
        items.append(rumps.separator)
        items.append(rumps.MenuItem(self.codex_line + "  -  click to open",
                                    callback=self._open_codex))
        items.append(rumps.MenuItem("Active org: %s" % org, callback=None))
        live = live_claude_sessions()
        if live:
            items.append(rumps.MenuItem(
                "%d live CLI session(s): switch applies in ~30s, not mid-reply"
                % len(live), callback=None))
        items.append(rumps.separator)
        items.append(rumps.MenuItem("Refresh", callback=self.refresh))
        items.append(rumps.MenuItem("Quit", callback=self._quit))
        self.menu.clear()
        for it in items:
            self.menu.add(it)

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
                log_click("menubar switch-to %s (%s) live_cli=%d"
                          % (n, label, len(live)))
                org, u8 = active_org()
                if live:
                    _notify("SwitchBar", "Switched to %s" % label,
                            "%d live CLI session(s): applies in ~30s, "
                            "not mid-reply." % len(live))
                else:
                    _notify("SwitchBar", "Switched to %s" % label,
                            "Active org: %s (%s...)" % (org, u8))
            else:
                _notify("SwitchBar", "Switch failed",
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
            _notify("SwitchBar", "Codex", "Opening Codex")
        else:
            _notify("SwitchBar", "Codex launch failed", (err or "check CODEX_LAUNCH_CMD")[:120])

    def _quit(self, _sender):
        log_click("menubar quit")
        rumps.quit_application()


if __name__ == "__main__":
    SwitchBar().run()
