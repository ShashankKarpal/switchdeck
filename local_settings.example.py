# Copy to local_settings.py (gitignored) and edit.
# Real org labels stay in the local copy only; committed code ships generic names.

SLOT_LABELS = {1: "primary", 2: "secondary"}   # menu row names
SHORT_LABELS = {1: "1", 2: "2"}                # menu bar title suffix

# CSWAP_BIN = "/Users/you/.local/bin/cswap"
# REFRESH_SECONDS = 300
# CODEX_REFRESH_SECONDS = 1800

# The Codex row is OFF by default; a stock install makes zero network calls.
# Uncomment to enable it (npx fetches ccusage from the npm registry):
# CODEX_USAGE_CMD = ["npx", "-y", "ccusage@latest", "codex", "--json"]

# Dry-run auto-switch narration is ON by default (notification plus click-log
# line when the engine's auto mode would have switched; nothing is switched).
# AUTO_NARRATE = False

# The menu bar title shows the active slot's tightest usage window, e.g.
# "⇄ 2 45%". Set False for the label only.
# TITLE_USAGE = False

# The Codex row launches Ghostty by default. Point this at any terminal:
# CODEX_LAUNCH_CMD = ["open", "-na", "Terminal", "--args", "-e", "codex"]
# CODEX_LAUNCH_CMD = ["open", "-na", "iTerm", "--args", "-e", "codex"]
