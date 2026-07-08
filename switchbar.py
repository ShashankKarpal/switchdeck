#!/usr/bin/env python3
"""SwitchBar (switchdeck v1.5): menu bar account switcher + usage deck.

Wraps cswap (claude-swap) to switch between two same-email Claude Code
accounts, shows per-account 5h/7d usage, and a read-only Codex usage row.
Owns only the surface; the engine is an upgradable dependency.
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
REFRESH_SECONDS = 300
CODEX_REFRESH_SECONDS = 1800
CODEX_USAGE_CMD = ["npx", "-y", "ccusage@latest", "codex", "--json"]
# Clicking the Codex row jumps into the tool: opens a terminal running codex.
CODEX_LAUNCH_CMD = ["open", "-na", "Ghostty", "--args", "-e", "codex"]

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
                mark = u"\u2713 " if acc.get("active") else "     "
                title = "%s%s  -  %s" % (mark, label, fmt_usage(acc.get("usage")))
                cb = None if acc.get("active") else self._make_switch(n, label)
                items.append(rumps.MenuItem(title, callback=cb))
        else:
            items.append(rumps.MenuItem("cswap unavailable - click to retry",
                                        callback=self.refresh))
        org, _u8 = active_org()
        self.title = u"\u21c4 %s" % _lbl(SHORT_LABELS, active_no, "?")
        items.append(rumps.separator)
        items.append(rumps.MenuItem(self.codex_line + "  -  click to open",
                                    callback=self._open_codex))
        items.append(rumps.MenuItem("Active org: %s" % org, callback=None))
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
                log_click("menubar switch-to %s (%s)" % (n, label))
                org, u8 = active_org()
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
