"""Unit tests for the pure functions in switchdeck.py.

Run from the repo root with the package venv, which provides rumps:

    ~/.switchdeck-venv/bin/python -m unittest discover -s tests -v

No engine, no network, no menu bar: everything here feeds hand-built
payloads shaped like cswap's --json output (schemaVersion 1, 0.25.0 and
0.26.0 fields) into the formatting and contract functions.
"""
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import switchdeck as sd  # noqa: E402


class EngineContract(unittest.TestCase):
    def setUp(self):
        self._saved = sd._ENGINE_VERSION

    def tearDown(self):
        sd._ENGINE_VERSION = self._saved

    def test_validated_engine_and_schema_pass(self):
        sd._ENGINE_VERSION = sd.VALIDATED_ENGINE
        self.assertIsNone(sd.engine_warning({"schemaVersion": sd.VALIDATED_SCHEMA_VERSION}))

    def test_version_drift_warns(self):
        sd._ENGINE_VERSION = "0.99.0"
        warn = sd.engine_warning({"schemaVersion": sd.VALIDATED_SCHEMA_VERSION})
        self.assertIn("0.99.0", warn)
        self.assertIn(sd.VALIDATED_ENGINE, warn)

    def test_schema_drift_warns(self):
        sd._ENGINE_VERSION = sd.VALIDATED_ENGINE
        warn = sd.engine_warning({"schemaVersion": 2})
        self.assertIn("schema 2", warn)

    def test_unknown_engine_version_is_not_a_warning(self):
        # A missing engine is the retry row's job, not the warning row's.
        sd._ENGINE_VERSION = None
        self.assertIsNone(sd.engine_warning(None))


class FormatUsage(unittest.TestCase):
    def test_fixed_order_and_labels(self):
        u = {"sevenDay": {"pct": 40.4}, "fiveHour": {"pct": 91.6}, "spend": {"pct": 10}}
        self.assertEqual(sd.fmt_usage(u), "5h 92% - 7d 40% - spend 10%")

    def test_scoped_windows_render_by_name_after_7d_and_unknown_dict_last(self):
        # 0.26.0 sends scoped as a list of per-model weekly windows carrying
        # a name; they render after 7d under that name. An unknown dict
        # window still renders under its raw key, last.
        u = {"fiveHour": {"pct": 5}, "spend": {"pct": 1},
             "scoped": [{"pct": 50, "name": "Fable"}, {"pct": 3}],
             "later": {"pct": 7}}
        self.assertEqual(sd.fmt_usage(u), "5h 5% - Fable 50% - scoped 3% - spend 1% - later 7%")

    def test_empty_or_wrong_type(self):
        self.assertEqual(sd.fmt_usage(None), "usage n/a")
        self.assertEqual(sd.fmt_usage({}), "usage n/a")


class RichUsage(unittest.TestCase):
    LIVE = {"fiveHour": {"pct": 25.0, "clock": "15:30", "countdown": "4h 27m"},
            "sevenDay": {"pct": 23.0, "clock": "Sep 7 17:30", "aheadOfPace": False,
                         "willLastToReset": True},
            "scoped": [{"pct": 45.0, "name": "Fable", "clock": "Sep 7 17:30",
                        "aheadOfPace": False, "willLastToReset": True}]}

    def test_reset_clock_follows_the_tightest_window(self):
        self.assertEqual(sd.fmt_usage_rich(self.LIVE),
                         "5h 25% - 7d 23% - Fable 45% (resets Sep 7 17:30) - on pace")

    def test_reset_clock_omitted_when_engine_gives_none(self):
        u = {"fiveHour": {"pct": 60}, "sevenDay": {"pct": 10}}
        self.assertEqual(sd.fmt_usage_rich(u), "5h 60% - 7d 10%")

    def test_pace_chip_states(self):
        self.assertIsNone(sd.pace_chip({"fiveHour": {"pct": 1}}))
        self.assertEqual(sd.pace_chip({"sevenDay": {"pct": 1, "aheadOfPace": False,
                                                    "willLastToReset": True}}), "on pace")
        self.assertEqual(sd.pace_chip({"sevenDay": {"pct": 1, "aheadOfPace": True,
                                                    "willLastToReset": True}}), "ahead of pace")
        # Any weekly window that will not last to its reset wins.
        self.assertEqual(sd.pace_chip({"sevenDay": {"pct": 1, "aheadOfPace": False,
                                                    "willLastToReset": True},
                                       "scoped": [{"pct": 90, "name": "Fable",
                                                   "aheadOfPace": True,
                                                   "willLastToReset": False}]}),
                         "will cap early")
        # 0.25.0 shape: no pace fields at all, no chip.
        self.assertIsNone(sd.pace_chip({"sevenDay": {"pct": 40}}))

    def test_usage_line_uses_rich_form_for_live_and_plain_for_last_good(self):
        acc = {"usage": self.LIVE, "usageAgeSeconds": 12}
        self.assertTrue(sd.usage_line(acc).endswith("(resets Sep 7 17:30) - on pace"))
        stale = {"usage": None, "usageStatus": "unavailable",
                 "lastGoodUsage": self.LIVE, "lastGoodAgeSeconds": 4000}
        self.assertEqual(sd.usage_line(stale),
                         "5h 25% - 7d 23% - Fable 45% (stale <1d, unavailable)")


class UsageLine(unittest.TestCase):
    def test_fresh_usage_has_no_marker(self):
        acc = {"usage": {"fiveHour": {"pct": 12}}, "usageAgeSeconds": 39.4}
        self.assertEqual(sd.usage_line(acc), "5h 12%")

    def test_old_usage_gets_age_marker(self):
        acc = {"usage": {"fiveHour": {"pct": 12}}, "usageAgeSeconds": 900}
        self.assertEqual(sd.usage_line(acc), "5h 12% (15m old)")
        acc["usageAgeSeconds"] = 7200
        self.assertEqual(sd.usage_line(acc), "5h 12% (2h old)")

    def test_missing_age_field_is_treated_as_fresh(self):
        # 0.25.0 rows have no usageAgeSeconds at all.
        acc = {"usage": {"fiveHour": {"pct": 12}}}
        self.assertEqual(sd.usage_line(acc), "5h 12%")

    def test_null_usage_falls_back_to_last_good_with_staleness(self):
        acc = {"usage": None, "usageStatus": "relogin_required",
               "lastGoodUsage": {"fiveHour": {"pct": 3}, "sevenDay": {"pct": 30}},
               "lastGoodAgeSeconds": 3 * 86400 + 5}
        self.assertEqual(sd.usage_line(acc), "5h 3% - 7d 30% (stale 3d, relogin required)")

    def test_null_usage_without_last_good(self):
        self.assertEqual(sd.usage_line({"usage": None, "usageStatus": "token_expired"}),
                         "usage n/a")


class SessionActivity(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.saved = sd.CLAUDE_PROJECTS_DIR
        sd.CLAUDE_PROJECTS_DIR = self.root

    def tearDown(self):
        sd.CLAUDE_PROJECTS_DIR = self.saved
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def _transcript(self, cwd, sid, age_seconds):
        d = os.path.join(self.root, sd.encode_project_dir(cwd))
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, sid + ".jsonl")
        with open(p, "w") as f:
            f.write("{}\n")
        import time
        t = time.time() - age_seconds
        os.utime(p, (t, t))
        return p

    def test_project_dir_encoding_matches_claude_code(self):
        self.assertEqual(sd.encode_project_dir("/Users/me/.local"), "-Users-me--local")
        self.assertEqual(sd.encode_project_dir("/Users/me/Desktop/Codex"),
                         "-Users-me-Desktop-Codex")

    def test_busy_when_transcript_written_recently(self):
        self._transcript("/Users/me/proj-a", "aaa", 2)
        self._transcript("/Users/me/proj-b", "bbb", 120)
        sessions = [{"pid": 1, "cwd": "/Users/me/proj-a", "sessionId": "aaa"},
                    {"pid": 2, "cwd": "/Users/me/proj-b", "sessionId": "bbb"},
                    {"pid": 3, "cwd": "/Users/me/proj-c", "sessionId": "ccc"}]  # no transcript
        act = sd.session_activity(sessions)
        self.assertEqual(act, {"live": 3, "busy": 1})

    def test_transcripts_are_never_opened(self):
        import builtins
        self._transcript("/Users/me/proj-a", "aaa", 1)
        real_open = builtins.open

        def guard(path, *a, **kw):
            if str(path).endswith(".jsonl"):
                raise AssertionError("transcript opened: %s" % path)
            return real_open(path, *a, **kw)

        builtins.open = guard
        try:
            act = sd.session_activity([{"pid": 1, "cwd": "/Users/me/proj-a",
                                        "sessionId": "aaa"}])
        finally:
            builtins.open = real_open
        self.assertEqual(act["busy"], 1)

    def test_malformed_session_entries_degrade_to_count_only(self):
        act = sd.session_activity([{"pid": 1}, "junk", None])
        self.assertEqual(act, {"live": 3, "busy": 0})

    def test_live_sessions_line(self):
        self.assertIsNone(sd.live_sessions_line({"live": 0, "busy": 0}))
        self.assertEqual(sd.live_sessions_line({"live": 2, "busy": 0}),
                         "2 live CLI session(s), idle: switch applies in ~30s, not mid-reply")
        self.assertEqual(sd.live_sessions_line({"live": 2, "busy": 1}),
                         "2 live CLI session(s), 1 busy: switch applies in ~30s, not mid-reply")


class DrivingWindow(unittest.TestCase):
    def test_picks_window_over_threshold(self):
        poll = {"threshold": 90, "windowsPct": {"1": {"fiveHour": 91, "sevenDay": 95}}}
        self.assertEqual(sd.driving_window(poll, 1), ("sevenDay", 95))

    def test_no_windows(self):
        self.assertEqual(sd.driving_window({"windowsPct": {}}, 1), (None, None))
        self.assertEqual(sd.driving_window(None, 1), (None, None))


class ClickLogMode(unittest.TestCase):
    def test_existing_world_readable_log_is_tightened(self):
        saved = sd.CLICK_LOG
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            os.chmod(path, 0o644)
            sd.CLICK_LOG = path
            sd.log_click("test line")
            mode = stat.S_IMODE(os.stat(path).st_mode)
            self.assertEqual(mode, 0o600)
            with open(path) as f:
                self.assertIn("test line", f.read())
        finally:
            sd.CLICK_LOG = saved
            os.unlink(path)

    def test_new_log_is_created_0600(self):
        saved = sd.CLICK_LOG
        d = tempfile.mkdtemp()
        path = os.path.join(d, "clicks.log")
        try:
            sd.CLICK_LOG = path
            sd.log_click("first")
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        finally:
            sd.CLICK_LOG = saved
            os.unlink(path)
            os.rmdir(d)


class NarrationOutcome(unittest.TestCase):
    POLL = {"event": "poll", "threshold": 90,
            "windowsPct": {"1": {"fiveHour": 91, "sevenDay": 40}}}

    def test_new_would_switch_notifies_and_sets_key(self):
        events = [self.POLL, {"event": "switch", "from": {"number": 1}, "to": {"number": 2}}]
        out = sd.narration_outcome(0, events, None)
        self.assertEqual(out.key, (1, 2, "fiveHour"))
        self.assertIn("would-switch 1->2 fiveHour at 91%", out.log_line)
        self.assertNotIn("deduped", out.log_line)
        self.assertIn("Would switch slot 1 to slot 2", out.notify_message)
        self.assertIsNone(out.menu_row)

    def test_same_condition_is_deduped_but_still_logged(self):
        events = [self.POLL, {"event": "switch", "from": {"number": 1}, "to": {"number": 2}}]
        out = sd.narration_outcome(0, events, (1, 2, "fiveHour"))
        self.assertEqual(out.key, (1, 2, "fiveHour"))
        self.assertIn("(deduped)", out.log_line)
        self.assertIsNone(out.notify_message)

    def test_no_switch_clears_key_silently(self):
        out = sd.narration_outcome(2, [self.POLL, {"event": "no-switch", "reason": "below"}],
                                   (1, 2, "fiveHour"))
        self.assertIsNone(out.key)
        self.assertIsNone(out.log_line)
        self.assertIsNone(out.notify_message)
        self.assertIsNone(out.menu_row)

    def test_error_logs_and_returns_menu_row_without_notification(self):
        out = sd.narration_outcome(1, [{"event": "error", "error": "engine down"}], None)
        self.assertIn("auto-dryrun error rc=1 engine down", out.log_line)
        self.assertIsNone(out.notify_message)
        self.assertTrue(out.menu_row.startswith("auto dry-run error: engine down"))
        self.assertIsNone(out.key)

    def test_blocked_by_exit_code(self):
        out = sd.narration_outcome(3, [], None)
        self.assertIn("blocked rc=3", out.log_line)
        self.assertTrue(out.menu_row.startswith("auto dry-run blocked"))


class RefreshPumpBehaviour(unittest.TestCase):
    def test_result_is_parked_once_and_taken_once(self):
        pump = sd.RefreshPump()
        self.assertTrue(pump.start(lambda: {"n": 1}))
        pump.join(5)
        self.assertEqual(pump.take(), {"n": 1})
        self.assertIsNone(pump.take())
        self.assertFalse(pump.busy)

    def test_overlapping_start_is_refused_while_in_flight(self):
        import threading
        gate = threading.Event()

        def slow():
            gate.wait(5)
            return "done"

        pump = sd.RefreshPump()
        self.assertTrue(pump.start(slow))
        self.assertTrue(pump.busy)
        self.assertFalse(pump.start(slow))
        gate.set()
        pump.join(5)
        self.assertEqual(pump.take(), "done")
        self.assertFalse(pump.busy)

    def test_exception_clears_in_flight_and_parks_error(self):
        def boom():
            raise RuntimeError("engine exploded")

        pump = sd.RefreshPump()
        self.assertTrue(pump.start(boom))
        pump.join(5)
        self.assertFalse(pump.busy)
        result = pump.take()
        self.assertIsInstance(result, sd.CollectError)
        self.assertIn("engine exploded", str(result))
        self.assertTrue(pump.start(lambda: 1))
        pump.join(5)


class CollectSnapshot(unittest.TestCase):
    def test_snapshot_uses_engine_functions_and_carries_all_fields(self):
        saved = (sd.cswap_list, sd.cswap_auto_dryrun, sd.active_org,
                 sd.live_claude_sessions, sd._ENGINE_VERSION, sd.AUTO_NARRATE)
        try:
            sd._ENGINE_VERSION = sd.VALIDATED_ENGINE
            sd.AUTO_NARRATE = True
            sd.cswap_list = lambda: {"schemaVersion": 1, "activeAccountNumber": 2,
                                     "accounts": [{"number": 2, "active": True,
                                                   "usage": {"fiveHour": {"pct": 9}}}]}
            sd.cswap_auto_dryrun = lambda: (2, [{"event": "no-switch"}])
            sd.active_org = lambda: ("Org", "abcd1234")
            sd.live_claude_sessions = lambda: [{"pid": 1}]
            snap = sd.collect_snapshot()
            self.assertEqual(snap["data"]["activeAccountNumber"], 2)
            self.assertIsNone(snap["warn"])
            self.assertEqual(snap["auto"], (2, [{"event": "no-switch"}]))
            self.assertEqual(snap["org"], "Org")
            self.assertEqual(snap["live"], 1)
            self.assertEqual(snap["busy"], 0)  # pid 1 has no transcript
        finally:
            (sd.cswap_list, sd.cswap_auto_dryrun, sd.active_org,
             sd.live_claude_sessions, sd._ENGINE_VERSION, sd.AUTO_NARRATE) = saved

    def test_narration_off_skips_the_dry_run(self):
        saved = (sd.cswap_list, sd.cswap_auto_dryrun, sd.active_org,
                 sd.live_claude_sessions, sd.AUTO_NARRATE)
        calls = []
        try:
            sd.AUTO_NARRATE = False
            sd.cswap_list = lambda: None
            sd.cswap_auto_dryrun = lambda: calls.append("dryrun")
            sd.active_org = lambda: ("?", "?")
            sd.live_claude_sessions = lambda: []
            snap = sd.collect_snapshot()
            self.assertIsNone(snap["auto"])
            self.assertEqual(calls, [])
        finally:
            (sd.cswap_list, sd.cswap_auto_dryrun, sd.active_org,
             sd.live_claude_sessions, sd.AUTO_NARRATE) = saved


if __name__ == "__main__":
    unittest.main()
