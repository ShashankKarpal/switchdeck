"""Prove the notification path end to end, inside a real rumps run loop.

Fires the exact banner a successful switch produces, using the app's own
_notify, ensure_notification_bundle, active_org and last_project. Run it
after any venv rebuild or Python change:

    ~/.switchdeck-venv/bin/python3 scripts/selftest_notify.py

Exits non-zero if the notification centre could not be reached, so a
silent notification path fails a check instead of failing in the dark.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rumps  # noqa: E402

import switchdeck as sd  # noqa: E402


class SelfTest(rumps.App):
    def __init__(self):
        super(SelfTest, self).__init__("SELFTEST", quit_button=None)
        self.code = 1
        self.timer = rumps.Timer(self.fire, 2)
        self.timer.start()

    def fire(self, _sender):
        self.timer.stop()
        org, u8 = sd.active_org()
        proj = sd.last_project()
        live = sd.live_claude_sessions()
        body = "Active org: %s (%s...)" % (org, u8)
        if proj:
            body = "%s Last project: %s." % (body, proj)
        print("org=%s uuid8=%s project=%s live_sessions=%d"
              % (org, u8, proj, len(live)))
        try:
            rumps.notification(sd.APP_NAME, "Self test", body)
            print("PASS: notification centre reached, banner posted")
            self.code = 0
        except Exception as e:  # noqa: BLE001
            print("FAIL: %s: %s" % (type(e).__name__, str(e).splitlines()[0]))
            print("falling back to osascript so you still see something")
            ok, detail = sd._notify_fallback(sd.APP_NAME, "Self test (fallback)", body)
            print("fallback ok=%s %s" % (ok, detail))
        rumps.quit_application()


if __name__ == "__main__":
    ok, detail = sd.ensure_notification_bundle()
    print("notification bundle: %s (%s)" % ("ok" if ok else "FAILED", detail))
    app = SelfTest()
    app.run()
    sys.exit(app.code)
