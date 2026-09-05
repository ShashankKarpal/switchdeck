#!/usr/bin/env bash
# Install or repair SwitchDeck: engine, venv, app bundle, LaunchAgent.
#
# Idempotent and safe to re-run. This script exists because of two incidents:
# 2026-08-24 morning, the venv was built against a Homebrew Python that was
# later removed, the LaunchAgent failed to spawn with exit code 78
# (EX_CONFIG), and the failure was invisible for days; 2026-08-24 afternoon,
# it turned out macOS only presents notification banners for real,
# LaunchServices-registered .app bundles, so every unbundled configuration
# filed notifications into Notification Center without ever showing one.
# One command now rebuilds every piece and proves it came up.
#
# What it builds:
#   ~/.switchdeck-venv          packages only (rumps, pyobjc UserNotifications)
#   ~/Applications/SwitchDeck.app  identity: a copy of the uv-managed static
#                               CPython as the bundle executable, Info.plist
#                               (com.shashankkarpal.switchdeck), icon, ad-hoc
#                               signature. Nothing else: codesign rejects
#                               data files outside Resources, so stdlib and
#                               site-packages are wired via PYTHONHOME and
#                               PYTHONPATH in the LaunchAgent instead.
#
# Usage:
#   scripts/install.sh              install or repair
#   scripts/install.sh --rebuild    also recreate the venv from scratch
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$HOME/.switchdeck-venv"
APP="$HOME/Applications/SwitchDeck.app"
APP_NAME="SwitchDeck"
BUNDLE_ID="com.shashankkarpal.switchdeck"
VERSION="2.0.0"
LABEL="com.shashank.switchdeck"
OLD_LABEL="com.shashank.switchbar"
AGENTS="$HOME/Library/LaunchAgents"
PLIST="$AGENTS/$LABEL.plist"
UID_NUM="$(id -u)"
REBUILD="${1:-}"

step() { printf '\n==> %s\n' "$1"; }
fail() { printf 'FAILED: %s\n' "$1" >&2; exit 1; }

command -v uv >/dev/null 2>&1 || fail "uv not found. Install it first: brew install uv"

step "Interpreter (uv-managed CPython; never a Homebrew one)"
PY="$(uv python find 3.14 2>/dev/null || true)"
[ -n "$PY" ] || fail "no uv-managed Python 3.14 found. Run: uv python install 3.14"
UVPY="$(cd "$(dirname "$PY")/.." && pwd)"
echo "interpreter: $PY"
echo "home: $UVPY"

step "Engine (claude-swap)"
if ! cswap --version >/dev/null 2>&1; then
  uv tool install claude-swap --python "$PY"
else
  echo "cswap present: $(cswap --version)"
fi

step "Virtual environment at $VENV (packages only)"
if [ "$REBUILD" = "--rebuild" ] || [ ! -x "$VENV/bin/python3" ]; then
  [ -d "$VENV" ] && mv "$VENV" "$VENV.old.$(date +%Y%m%d%H%M%S)"
  uv venv --python "$PY" "$VENV"
fi
uv pip install --python "$VENV/bin/python3" --quiet \
  'rumps>=0.4.0' 'pyobjc-framework-UserNotifications'
"$VENV/bin/python3" -c 'import rumps, UserNotifications' \
  || fail "rumps/UserNotifications not importable in the venv"

step "App bundle at $APP"
# Rebuilt from scratch every run: it holds no state, and a stale interpreter
# copy inside it is exactly the drift this script exists to prevent. The
# copied binary diverges from uv upgrades until the next install.sh run;
# scripts/selftest_notify.py proves the shipped configuration still works.
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$UVPY/bin/python3.14" "$APP/Contents/MacOS/$APP_NAME"
cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_NAME</string>
  <key>CFBundleExecutable</key><string>$APP_NAME</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF
if [ -d "$REPO/design/app-icons/macos/AppIcon.appiconset" ]; then
  ICONSET="$(mktemp -d)/AppIcon.iconset"
  cp -R "$REPO/design/app-icons/macos/AppIcon.appiconset" "$ICONSET"
  rm -f "$ICONSET/Contents.json"
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
fi
codesign -s - --force "$APP"
codesign -v "$APP" || fail "bundle signature invalid"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"

step "Local settings"
if [ ! -f "$REPO/local_settings.py" ]; then
  cp "$REPO/local_settings.example.py" "$REPO/local_settings.py"
  echo "created local_settings.py from the example; edit it to set real labels"
else
  echo "local_settings.py present, left alone"
fi

step "LaunchAgent $LABEL"
mkdir -p "$AGENTS"
sed -e "s|/Users/YOU|$HOME|g" "$REPO/com.shashank.switchdeck.plist" > "$PLIST.new"
/usr/libexec/PlistBuddy -c "Set :ProgramArguments:0 $APP/Contents/MacOS/$APP_NAME" "$PLIST.new"
/usr/libexec/PlistBuddy -c "Set :ProgramArguments:1 $REPO/switchdeck.py" "$PLIST.new"
/usr/libexec/PlistBuddy -c "Set :WorkingDirectory $REPO" "$PLIST.new"
/usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:PYTHONHOME $UVPY" "$PLIST.new"
/usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:PYTHONPATH $VENV/lib/python3.14/site-packages" "$PLIST.new"
plutil -lint "$PLIST.new" >/dev/null || fail "rendered plist is invalid"
mv "$PLIST.new" "$PLIST"

# Retire the pre-rename label if it is still around, or two copies of the
# app fight over the menu bar.
if launchctl print "gui/$UID_NUM/$OLD_LABEL" >/dev/null 2>&1; then
  echo "booting out $OLD_LABEL"
  launchctl bootout "gui/$UID_NUM/$OLD_LABEL" || true
fi
[ -f "$AGENTS/$OLD_LABEL.plist" ] && mv "$AGENTS/$OLD_LABEL.plist" "$AGENTS/$OLD_LABEL.plist.retired"

launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
sleep 1
launchctl bootstrap "gui/$UID_NUM" "$PLIST"
launchctl kickstart "gui/$UID_NUM/$LABEL" 2>/dev/null || true

step "Verify"
sleep 5
if ! pgrep -f "switchdeck.py" >/dev/null; then
  launchctl print "gui/$UID_NUM/$LABEL" 2>&1 | grep -E 'last exit|state' || true
  fail "the app is not running. Check ~/switchdeck.log and the exit code above."
fi
echo "running: pid $(pgrep -f switchdeck.py | head -1)"
tail -3 "$HOME/switchdeck-clicks.log" 2>/dev/null || true
printf '\nDone. Look for the arrow item in the menu bar. On first run macOS\n'
printf 'asks to allow SwitchDeck notifications; the answer lands in the\n'
printf 'click log. scripts/selftest_notify.py re-proves delivery any time.\n'
