"""Prove the notification path end to end, inside a real rumps run loop,
under the app's own bundle identity.

Run it THROUGH THE BUNDLE, exactly as the LaunchAgent does:

    UVPY=$HOME/.local/share/uv/python/cpython-3.14.7-macos-aarch64-none
    env PYTHONHOME=$UVPY \
        PYTHONPATH=$HOME/.switchdeck-venv/lib/python3.14/site-packages \
        "$HOME/Applications/SwitchDeck.app/Contents/MacOS/SwitchDeck" \
        scripts/selftest_notify.py

Run under a bare venv interpreter it still works, but it then tests the
fallback identity, not the shipped configuration. Exit codes: 0 the modern
path posted under granted authorization; 2 authorization is denied or
undetermined (the post may not present a banner); 1 the modern path failed
outright (the app would fall back to legacy and osascript, with evidence
in the click log).
"""
import os
import sys
import time

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
        try:
            import UserNotifications as UN
            from Foundation import NSBundle, NSRunLoop, NSDate
            print("bundle id:", NSBundle.mainBundle().bundleIdentifier())
            center = UN.UNUserNotificationCenter.currentNotificationCenter()
            state = {}

            def auth_cb(granted, error):
                state["granted"] = granted
                state["error"] = error

            opts = UN.UNAuthorizationOptionAlert | UN.UNAuthorizationOptionSound
            center.requestAuthorizationWithOptions_completionHandler_(opts, auth_cb)
            deadline = time.time() + 30
            while "granted" not in state and time.time() < deadline:
                NSRunLoop.currentRunLoop().runUntilDate_(
                    NSDate.dateWithTimeIntervalSinceNow_(0.25))
            granted = state.get("granted")
            print("authorization granted=%s error=%s"
                  % (granted, state.get("error")))

            org, u8 = sd.active_org()
            proj = sd.last_project()
            body = "Active org: %s (%s...)" % (org, u8)
            if proj:
                body = "%s Last project: %s." % (body, proj)
            sd._notify_modern(sd.APP_NAME, "Self test", body)
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(2.0))
            if granted:
                print("PASS: modern path posted under granted authorization")
                self.code = 0
            else:
                print("POSTED BUT NOT AUTHORIZED: enable %s in System "
                      "Settings > Notifications" % sd.APP_NAME)
                self.code = 2
        except Exception as e:  # noqa: BLE001
            print("FAIL: %s: %s" % (type(e).__name__, str(e).splitlines()[0]))
            print("the app itself would fall back to legacy and osascript")
        rumps.quit_application()


if __name__ == "__main__":
    ok, detail = sd.ensure_notification_bundle()
    print("notification bundle: %s (%s)" % ("ok" if ok else "FAILED", detail))
    app = SelfTest()
    app.run()
    sys.exit(app.code)
