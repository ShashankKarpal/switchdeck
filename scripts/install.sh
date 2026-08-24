#!/usr/bin/env bash
# Install or repair SwitchDeck: venv, engine, notification bundle, LaunchAgent.
#
# Idempotent and safe to re-run. This script exists because of an incident on
# 2026-08-24: the venv was built against a Homebrew Python that was later
# removed, the LaunchAgent then failed to spawn with exit code 78 (EX_CONFIG),
# and because a menu bar app has no window, the failure was invisible for
# days. Rebuilding by hand also loses the Info.plist that notifications
# depend on. One command now rebuilds every piece and proves it came up.
#
# Usage:
#   scripts/install.sh              install or repair
#   scripts/install.sh --rebuild    also recreate the venv from scratch
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$HOME/.switchdeck-venv"
LABEL="com.shashank.switchdeck"
OLD_LABEL="com.shashank.switchbar"
AGENTS="$HOME/Library/LaunchAgents"
PLIST="$AGENTS/$LABEL.plist"
UID_NUM="$(id -u)"
REBUILD="${1:-}"

step() { printf '\n==> %s\n' "$1"; }
fail() { printf 'FAILED: %s\n' "$1" >&2; exit 1; }

command -v uv >/dev/null 2>&1 || fail "uv not found. Install it first: brew install uv"

step "Engine (claude-swap)"
# Pinned interpreter for the tool too: a uv-managed Python cannot be removed
# by a Homebrew upgrade, which is what broke this install once already.
PY="$(uv python find 3.14 2>/dev/null || true)"
[ -n "$PY" ] || PY="$(uv python find 3.13 2>/dev/null || true)"
[ -n "$PY" ] || fail "no uv-managed Python 3.13+ found. Run: uv python install 3.14"
echo "interpreter: $PY"
if ! cswap --version >/dev/null 2>&1; then
  uv tool install claude-swap --python "$PY"
else
  echo "cswap present: $(cswap --version)"
fi

step "Virtual environment at $VENV"
if [ "$REBUILD" = "--rebuild" ] || [ ! -x "$VENV/bin/python3" ]; then
  [ -d "$VENV" ] && mv "$VENV" "$VENV.old.$(date +%Y%m%d%H%M%S)"
  uv venv --python "$PY" "$VENV"
fi
uv pip install --python "$VENV/bin/python3" --quiet 'rumps>=0.4.0'
"$VENV/bin/python3" -c 'import rumps' || fail "rumps not importable in the venv"

step "Notification bundle"
# rumps resolves its notification centre through an Info.plist beside the
# interpreter. Without it every notification raises and nothing draws. The
# app writes this at startup too; doing it here means a fresh install
# notifies on its very first switch.
"$VENV/bin/python3" - <<'PY'
import os, plistlib, sys
p = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "Info.plist")
plistlib.dump({"CFBundleIdentifier": "com.shashank.switchdeck",
               "CFBundleName": "SwitchDeck"}, open(p, "wb"))
print("wrote", p)
PY

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
# Point at this clone wherever it actually is, not the template's location.
/usr/libexec/PlistBuddy -c "Set :ProgramArguments:1 $REPO/switchdeck.py" "$PLIST.new"
/usr/libexec/PlistBuddy -c "Set :WorkingDirectory $REPO" "$PLIST.new"
/usr/libexec/PlistBuddy -c "Set :ProgramArguments:0 $VENV/bin/python3" "$PLIST.new"
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
launchctl bootstrap "gui/$UID_NUM" "$PLIST"
launchctl kickstart -k "gui/$UID_NUM/$LABEL"

step "Verify"
sleep 5
if ! pgrep -f "switchdeck.py" >/dev/null; then
  launchctl print "gui/$UID_NUM/$LABEL" 2>&1 | grep -E 'last exit|state' || true
  fail "the app is not running. Check ~/switchdeck.log and the exit code above."
fi
echo "running: pid $(pgrep -f switchdeck.py | head -1)"
tail -3 "$HOME/switchdeck-clicks.log" 2>/dev/null || true
printf '\nDone. Look for the arrow item in the menu bar.\n'
