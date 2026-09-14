"""Tests for scripts/make_bundle.sh, the bundle builder shared by the menu
bar apps on this Mac. Builds real bundles into a temp dir with --no-register
(no LaunchServices registration is left behind), signs them ad hoc, and runs
the copied interpreter once. Needs the uv-managed CPython 3.14 the fleet
pins; skipped when `uv python find 3.14` finds none.

    ~/.switchdeck-venv/bin/python -m unittest discover -s tests -v
"""
import os
import plistlib
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "make_bundle.sh")
ICONSET = os.path.join(REPO, "design", "app-icons", "macos", "AppIcon.appiconset")


def _uv_home():
    try:
        out = subprocess.run(["uv", "python", "find", "3.14"], capture_output=True,
                             text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return os.path.dirname(os.path.dirname(os.path.realpath(out.stdout.strip())))


def _clean_env():
    env = dict(os.environ)
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + os.path.expanduser("~/.local/bin")
    return env


@unittest.skipUnless(_uv_home(), "uv-managed CPython 3.14 not installed")
class MakeBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = _uv_home()
        cls.tmp = tempfile.mkdtemp(prefix="make-bundle-test.")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build(self, *extra, name="Demo Tile", check=True):
        cmd = [SCRIPT, "--name", name, "--bundle-id", "com.example.demotile",
               "--python-home", self.home, "--out", self.tmp, "--no-register", *extra]
        p = subprocess.run(cmd, capture_output=True, text=True, env=_clean_env(), timeout=120)
        if check:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def info(self, name="Demo Tile"):
        with open(os.path.join(self.tmp, name + ".app", "Contents", "Info.plist"), "rb") as f:
            return plistlib.load(f)

    def test_builds_signed_bundle_and_prints_executable(self):
        p = self.build()
        exe = p.stdout.strip()
        self.assertEqual(exe, os.path.join(self.tmp, "Demo Tile.app", "Contents", "MacOS", "Demo Tile"))
        self.assertTrue(os.access(exe, os.X_OK))
        app = os.path.dirname(os.path.dirname(os.path.dirname(exe)))
        self.assertTrue(app.endswith("Demo Tile.app"), app)
        self.assertEqual(subprocess.run(["codesign", "-v", app], capture_output=True).returncode, 0)
        info = self.info()
        self.assertEqual(info["CFBundleIdentifier"], "com.example.demotile")
        self.assertEqual(info["CFBundleExecutable"], "Demo Tile")
        self.assertEqual(info["CFBundleShortVersionString"], "1.0")
        self.assertTrue(info["LSUIElement"])
        self.assertNotIn("CFBundleIconFile", info)
        self.assertFalse(os.path.exists(os.path.join(app, "Contents", "Resources", "AppIcon.icns")))

    def test_copied_interpreter_runs_against_its_home(self):
        exe = self.build().stdout.strip()
        env = _clean_env()
        env["PYTHONHOME"] = self.home
        got = subprocess.run([exe, "-c", "import sys; print(sys.version)"], capture_output=True,
                             text=True, env=env, timeout=30)
        want = subprocess.run([os.path.join(self.home, "bin", "python3.14"), "-c",
                               "import sys; print(sys.version)"], capture_output=True,
                              text=True, env=env, timeout=30)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(got.stdout, want.stdout)

    @unittest.skipUnless(os.path.isdir(ICONSET), "repo iconset missing")
    def test_iconset_becomes_icns_and_icon_key(self):
        self.build("--iconset", ICONSET, "--version", "2.0.0")
        info = self.info()
        self.assertEqual(info["CFBundleIconFile"], "AppIcon")
        self.assertEqual(info["CFBundleVersion"], "2.0.0")
        icns = os.path.join(self.tmp, "Demo Tile.app", "Contents", "Resources", "AppIcon.icns")
        self.assertGreater(os.path.getsize(icns), 1000)

    def test_key_order_matches_the_shipped_bundles(self):
        self.build()
        with open(os.path.join(self.tmp, "Demo Tile.app", "Contents", "Info.plist")) as f:
            keys = [line.split("<key>")[1].split("</key>")[0] for line in f if "<key>" in line]
        self.assertEqual(keys, ["CFBundleIdentifier", "CFBundleName", "CFBundleDisplayName",
                                "CFBundleExecutable", "CFBundlePackageType",
                                "CFBundleShortVersionString", "CFBundleVersion",
                                "LSUIElement", "NSHighResolutionCapable"])

    def test_rebuild_replaces_a_stale_bundle(self):
        exe = self.build().stdout.strip()
        stale = os.path.join(os.path.dirname(exe), "leftover")
        with open(stale, "w") as f:
            f.write("x")
        self.build()
        self.assertFalse(os.path.exists(stale))

    def test_refuses_bad_input(self):
        self.assertNotEqual(self.build("--iconset", "/nonexistent", check=False).returncode, 0)
        self.assertNotEqual(self.build(name="a/b", check=False).returncode, 0)
        p = subprocess.run([SCRIPT, "--name", "X", "--out", self.tmp, "--no-register"],
                           capture_output=True, text=True, env=_clean_env())
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("required", p.stderr)
        p = subprocess.run([SCRIPT, "--name", "X", "--bundle-id", "b", "--python-home", "/nonexistent",
                            "--out", self.tmp, "--no-register"], capture_output=True, text=True,
                           env=_clean_env())
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("interpreter", p.stderr)

    def test_installer_uses_the_shared_builder(self):
        with open(os.path.join(REPO, "scripts", "install.sh")) as f:
            text = f.read()
        self.assertIn("make_bundle.sh", text)
        self.assertNotIn("codesign -s - --force", text)


if __name__ == "__main__":
    unittest.main()
