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

    def test_scoped_list_is_ignored_and_unknown_dict_is_appended(self):
        # 0.26.0 sends scoped as a list of per-model windows; it must not
        # break the row. An unknown dict window renders under its raw key.
        u = {"fiveHour": {"pct": 5}, "scoped": [{"pct": 50}], "later": {"pct": 7}}
        self.assertEqual(sd.fmt_usage(u), "5h 5% - later 7%")

    def test_empty_or_wrong_type(self):
        self.assertEqual(sd.fmt_usage(None), "usage n/a")
        self.assertEqual(sd.fmt_usage({}), "usage n/a")


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


if __name__ == "__main__":
    unittest.main()
