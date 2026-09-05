"""Unit tests for desktop_slots.py: the pure parts of the Desktop app slot
shims. No swiftc, no codesign, no Claude launch; build_shim itself is
exercised live by scripts/desktop_slots.py and recorded in CLAUDE.md.

    ~/.switchdeck-venv/bin/python -m unittest discover -s tests -v
"""
import os
import plistlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import desktop_slots as ds  # noqa: E402


def _bundle(root, name, info):
    app = os.path.join(root, name)
    os.makedirs(os.path.join(app, "Contents", "MacOS"))
    with open(os.path.join(app, "Contents", "Info.plist"), "wb") as f:
        plistlib.dump(info, f)
    return app


class Naming(unittest.TestCase):
    def test_shim_name_is_one_component_and_never_claude(self):
        self.assertEqual(ds.shim_name("kk2"), "Claude kk2.app")
        for bad in ("", "Claude", "claude", "a/b", "  "):
            with self.assertRaises(ValueError):
                ds.shim_name(bad)

    def test_profile_dir_is_a_sibling_of_claude_not_inside_it(self):
        p = ds.profile_dir(2)
        self.assertEqual(os.path.basename(p), "Claude Slot 2")
        self.assertEqual(os.path.dirname(p), ds.PROFILE_ROOT)
        self.assertNotIn("/Claude/", p)


class InfoPlist(unittest.TestCase):
    def test_marker_profile_and_identity(self):
        info = ds.shim_info(1, "kk1")
        self.assertEqual(info[ds.MARKER_KEY], 1)
        self.assertEqual(info[ds.PROFILE_KEY], ds.profile_dir(1))
        self.assertEqual(info["CFBundleIdentifier"], ds.BUNDLE_ID_PREFIX + ".slot1")
        self.assertEqual(info["CFBundleExecutable"], "launcher")
        self.assertEqual(info[ds.CLAUDE_KEY], ds.CLAUDE_APP)
        self.assertTrue(info["LSUIElement"])


class Marker(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_only_marked_bundles_are_ours(self):
        ours = _bundle(self.root, "Claude kk2.app", ds.shim_info(2, "kk2"))
        _bundle(self.root, "Claude kk1.app", {"CFBundleIdentifier": "x"})  # name lies
        _bundle(self.root, "Other.app", {ds.MARKER_KEY: True})  # bool is not a slot
        os.makedirs(os.path.join(self.root, "Broken.app"))  # no plist at all
        self.assertEqual(ds.read_marker(ours), 2)
        self.assertIsNone(ds.read_marker(os.path.join(self.root, "Claude kk1.app")))
        self.assertIsNone(ds.read_marker(os.path.join(self.root, "Other.app")))
        self.assertIsNone(ds.read_marker(os.path.join(self.root, "Broken.app")))
        found = ds.find_shims(self.root)
        self.assertEqual([(s, os.path.basename(p)) for s, p, _ in found],
                         [(2, "Claude kk2.app")])
        self.assertEqual(found[0][2], ds.profile_dir(2))

    def test_remove_touches_only_marked_bundles(self):
        _bundle(self.root, "Claude kk2.app", ds.shim_info(2, "kk2"))
        keep = _bundle(self.root, "Claude kk1.app", {"CFBundleIdentifier": "x"})
        removed = ds.remove_shims(self.root)
        self.assertEqual([os.path.basename(p) for p in removed], ["Claude kk2.app"])
        self.assertTrue(os.path.isdir(keep))

    def test_build_refuses_to_replace_an_unmarked_bundle(self):
        _bundle(self.root, "Claude kk1.app", {"CFBundleIdentifier": "x"})
        with self.assertRaises(RuntimeError):
            ds.build_shim(1, "kk1", apps_dir=self.root, claude_app=self.root)


class RunningDetection(unittest.TestCase):
    PROF = "/Users/me/Library/Application Support/Claude Slot 2"

    def test_browser_process_wins_helpers_are_ignored(self):
        lines = ["4100 /Applications/Claude.app/Contents/Frameworks/Claude Helper.app/"
                 "Contents/MacOS/Claude Helper --type=gpu --user-data-dir=%s" % self.PROF,
                 "4099 /Applications/Claude.app/Contents/MacOS/Claude --user-data-dir=%s"
                 % self.PROF]
        seen = {}

        def fake(pattern):
            seen["pattern"] = pattern
            return lines

        self.assertEqual(ds.running_pid(self.PROF, fake), 4099)
        # Anchored and escaped: a longer profile path cannot satisfy this one.
        self.assertTrue(seen["pattern"].endswith("( |$)"))
        self.assertIn("Application\\ Support", seen["pattern"])

    def test_no_match_is_none(self):
        self.assertIsNone(ds.running_pid(self.PROF, lambda p: []))
        self.assertIsNone(ds.running_pid(self.PROF, lambda p: ["junk"]))


class StatusAndRows(unittest.TestCase):
    def test_status_and_row_titles(self):
        root = tempfile.mkdtemp()
        try:
            _bundle(root, "Claude kk1.app", ds.shim_info(1, "kk1"))
            _bundle(root, "Claude kk2.app", ds.shim_info(2, "kk2"))
            running = {ds.profile_dir(2)}
            st = ds.status(root, lambda pat: ["77 /Applications/Claude.app/Contents/MacOS/"
                                              "Claude --user-data-dir=" + ds.profile_dir(2)]
                           if any(p in pat.replace("\\", "") for p in running) else [])
            self.assertEqual([(e["slot"], e["running"]) for e in st], [(1, False), (2, True)])
            self.assertEqual(ds.desktop_row_title(st[0], "kk1"), "Open Desktop: kk1")
            self.assertEqual(ds.desktop_row_title(st[1], "kk2"), "Open Desktop: kk2 (running)")
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
