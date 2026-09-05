"""Desktop app slots: one small launcher bundle per account slot that opens
Claude Desktop on its own profile folder, so two accounts can run side by
side on one Mac.

How it works (verified on Claude Desktop 1.44121.2, 2026-09-05):

- Claude Desktop is an Electron app and honours the Chromium flag
  `--user-data-dir=<folder>`. Launched through `open -n -a Claude --args
  --user-data-dir=<folder>` it starts ONE new instance on that folder and
  leaves the main instance alone. Running the binary directly instead of
  through `open -n` once produced a stray second instance on the MAIN
  profile, which is the one dangerous state (two apps writing one profile),
  so the launcher only ever uses `open -n`.
- Claude Desktop never refuses a second instance on the same profile, so
  the launcher checks first: if a Claude is already running on this slot's
  folder it is brought to the front instead of launched again. Helper
  processes repeat the flag, so only the browser process (path ending in
  MacOS/Claude) counts, and the match is anchored because one profile path
  can be a prefix of another.
- Each shim is a real .app in ~/Applications with a compiled Swift launcher
  as its executable, ad-hoc signed, carrying the marker key
  SwitchDeckDesktopSlot in Info.plist. Anything here that removes or
  rebuilds a bundle first checks that marker; an unmarked bundle is never
  touched, whatever its name (the graft rule, learned there the hard way).
- The profile folder is `~/Library/Application Support/Claude Slot <n>`:
  one plain component beside Claude's own profile, never inside it, never
  named Claude. It is created by Claude on first launch and never deleted by
  this module; removing a profile is an owner action.
- The engine (cswap) is not involved. Claude Code's command line keeps one
  login for the whole machine; the desktop profiles hold their own logins.
  Switching the CLI account and opening a desktop slot are independent.

This module holds the pure parts (plist, marker check, process parsing, row
text) so they can be unit-tested; scripts/desktop_slots.py is the command
line that builds, removes and reports, and switchdeck.py reads status() for
its menu rows.
"""
import os
import plistlib
import re
import shutil
import subprocess
import tempfile

HOME = os.path.expanduser("~")
CLAUDE_APP = "/Applications/Claude.app"
APPS_DIR = os.path.join(HOME, "Applications")
PROFILE_ROOT = os.path.join(HOME, "Library", "Application Support")
MARKER_KEY = "SwitchDeckDesktopSlot"
PROFILE_KEY = "SwitchDeckProfileDir"
CLAUDE_KEY = "SwitchDeckClaudeApp"
VERSION_KEY = "SwitchDeckShimVersion"
SHIM_VERSION = 1
BUNDLE_ID_PREFIX = "com.shashankkarpal.switchdeck.desktop"
SWITCHDECK_ICON = os.path.join(APPS_DIR, "SwitchDeck.app", "Contents", "Resources",
                               "AppIcon.icns")

# Swift source of the launcher. Compiled per shim by build_shim(); the
# profile folder and the Claude path are read from the shim's own
# Info.plist at run time, so the binary is identical across slots and the
# plist is the single place a slot is described.
LAUNCHER_SWIFT = r'''
import AppKit
import Foundation

let info = Bundle.main.infoDictionary ?? [:]
guard let profile = info["SwitchDeckProfileDir"] as? String, !profile.isEmpty else {
    FileHandle.standardError.write("SwitchDeck shim: SwitchDeckProfileDir missing\n".data(using: .utf8)!)
    exit(64)
}
let claude = (info["SwitchDeckClaudeApp"] as? String) ?? "/Applications/Claude.app"

func run(_ path: String, _ args: [String]) -> (Int32, String) {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: path)
    p.arguments = args
    let pipe = Pipe()
    p.standardOutput = pipe
    p.standardError = FileHandle.nullDevice
    do { try p.run() } catch { return (127, "") }
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    p.waitUntilExit()
    return (p.terminationStatus, String(decoding: data, as: UTF8.self))
}

// Already open on this profile? Only the browser process counts (helpers
// repeat the flag), and the match is anchored so a longer profile path
// cannot satisfy a shorter one.
let pattern = "MacOS/Claude --user-data-dir=" + NSRegularExpression.escapedPattern(for: profile) + "( |$)"
let (rc, out) = run("/usr/bin/pgrep", ["-f", "--", pattern])
if rc == 0 {
    for line in out.split(separator: "\n") {
        if let pid = Int32(line.trimmingCharacters(in: .whitespaces)),
           let app = NSRunningApplication(processIdentifier: pid) {
            app.activate(options: [.activateIgnoringOtherApps])
            exit(0)
        }
    }
}
let (orc, _) = run("/usr/bin/open", ["-n", "-a", claude, "--args", "--user-data-dir=" + profile])
exit(orc == 0 ? 0 : 1)
'''


def profile_dir(slot):
    return os.path.join(PROFILE_ROOT, "Claude Slot %d" % int(slot))


def shim_name(short_label):
    """'Claude <label>.app'. The label is one plain component: no path
    separators, and never 'Claude' alone, which would shadow the real app."""
    label = str(short_label).strip()
    if not label or "/" in label or label.lower() == "claude":
        raise ValueError("bad slot label for a shim name: %r" % short_label)
    return "Claude %s.app" % label


def shim_info(slot, short_label, claude_app=CLAUDE_APP):
    slot = int(slot)
    return {
        "CFBundleName": "Claude %s" % short_label,
        "CFBundleDisplayName": "Claude %s" % short_label,
        "CFBundleIdentifier": "%s.slot%d" % (BUNDLE_ID_PREFIX, slot),
        "CFBundleExecutable": "launcher",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "%d" % SHIM_VERSION,
        "CFBundleVersion": "%d" % SHIM_VERSION,
        "CFBundleIconFile": "AppIcon",
        "LSMinimumSystemVersion": "13.0",
        "LSUIElement": True,  # the launcher exits at once; no Dock bounce of its own
        MARKER_KEY: slot,
        PROFILE_KEY: profile_dir(slot),
        CLAUDE_KEY: claude_app,
        VERSION_KEY: SHIM_VERSION,
    }


def read_marker(bundle_path):
    """The slot number if this bundle is one of ours, else None. Reads
    Contents/Info.plist only; never trusts the name."""
    try:
        with open(os.path.join(bundle_path, "Contents", "Info.plist"), "rb") as f:
            info = plistlib.load(f)
    except Exception:  # noqa: BLE001 - not a bundle we can read, so not ours
        return None
    slot = info.get(MARKER_KEY)
    return int(slot) if isinstance(slot, int) and not isinstance(slot, bool) else None


def find_shims(apps_dir=APPS_DIR):
    """[(slot, bundle path, profile dir)] for every marked bundle, by slot."""
    out = []
    try:
        names = os.listdir(apps_dir)
    except OSError:
        return out
    for name in names:
        if not name.endswith(".app"):
            continue
        path = os.path.join(apps_dir, name)
        slot = read_marker(path)
        if slot is None:
            continue
        try:
            with open(os.path.join(path, "Contents", "Info.plist"), "rb") as f:
                prof = plistlib.load(f).get(PROFILE_KEY) or profile_dir(slot)
        except Exception:  # noqa: BLE001
            prof = profile_dir(slot)
        out.append((slot, path, prof))
    return sorted(out)


def _pgrep_lines(pattern):
    try:
        p = subprocess.run(["/usr/bin/pgrep", "-fl", "--", pattern],
                           capture_output=True, text=True, timeout=10)
    except Exception:  # noqa: BLE001
        return []
    return p.stdout.splitlines() if p.returncode == 0 else []


def running_pid(profile, pgrep_lines=_pgrep_lines):
    """PID of the Claude browser process on this profile, or None. The
    pattern keeps helpers out (they repeat the flag but their path is
    Claude Helper) and anchors the folder."""
    pattern = "MacOS/Claude --user-data-dir=%s( |$)" % re.escape(profile)
    for line in pgrep_lines(pattern):
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and "Claude Helper" not in parts[1]:
            try:
                return int(parts[0])
            except ValueError:
                continue
    return None


def status(apps_dir=APPS_DIR, pgrep_lines=_pgrep_lines):
    """[{'slot','path','profile','running'}] for every installed shim."""
    return [{"slot": slot, "path": path, "profile": prof,
             "running": running_pid(prof, pgrep_lines) is not None}
            for slot, path, prof in find_shims(apps_dir)]


def desktop_row_title(entry, label):
    """Menu row text for one shim: 'Open Desktop: kk2 (running)'."""
    return "Open Desktop: %s%s" % (label, " (running)" if entry.get("running") else "")


def open_shim(path):
    """Launch the shim like a double-click; the launcher decides whether
    to activate or start."""
    try:
        return subprocess.run(["/usr/bin/open", "-a", path], capture_output=True,
                              text=True, timeout=15).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _run(cmd, cwd=None):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return p.returncode, (p.stdout + p.stderr).strip()


def build_shim(slot, short_label, apps_dir=APPS_DIR, claude_app=CLAUDE_APP,
               icon_path=SWITCHDECK_ICON, swiftc="xcrun"):
    """Assemble one shim in a temp dir, compile and sign its launcher, then
    move it into place. Refuses to replace a bundle at the destination that
    does not carry our marker. Returns the bundle path; raises on failure."""
    dest = os.path.join(apps_dir, shim_name(short_label))
    if os.path.exists(dest) and read_marker(dest) is None:
        raise RuntimeError("refusing to replace an unmarked bundle: %s" % dest)
    if not os.path.isdir(claude_app):
        raise RuntimeError("Claude Desktop not found at %s" % claude_app)
    tmp = tempfile.mkdtemp(prefix="switchdeck-shim-")
    try:
        app = os.path.join(tmp, os.path.basename(dest))
        macos = os.path.join(app, "Contents", "MacOS")
        res = os.path.join(app, "Contents", "Resources")
        os.makedirs(macos)
        os.makedirs(res)
        with open(os.path.join(app, "Contents", "Info.plist"), "wb") as f:
            plistlib.dump(shim_info(slot, short_label, claude_app), f)
        src = os.path.join(tmp, "launcher.swift")
        with open(src, "w") as f:
            f.write(LAUNCHER_SWIFT)
        exe = os.path.join(macos, "launcher")
        cmd = ([swiftc, "swiftc"] if swiftc == "xcrun" else [swiftc]) + \
            ["-O", "-framework", "AppKit", src, "-o", exe]
        rc, out = _run(cmd)
        if rc != 0:
            raise RuntimeError("swiftc failed (%d): %s" % (rc, out[-400:]))
        if icon_path and os.path.exists(icon_path):
            shutil.copy2(icon_path, os.path.join(res, "AppIcon.icns"))
        rc, out = _run(["/usr/bin/codesign", "-s", "-", "--force", app])
        if rc != 0:
            raise RuntimeError("codesign failed (%d): %s" % (rc, out[-400:]))
        rc, out = _run(["/usr/bin/codesign", "-v", app])
        if rc != 0:
            raise RuntimeError("signature invalid (%d): %s" % (rc, out[-400:]))
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.move(app, dest)
        return dest
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def remove_shims(apps_dir=APPS_DIR):
    """Delete every marked shim bundle. Profile folders are left alone."""
    removed = []
    for _slot, path, _prof in find_shims(apps_dir):
        shutil.rmtree(path)
        removed.append(path)
    return removed
