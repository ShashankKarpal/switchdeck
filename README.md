<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)"  srcset="design/github/readme-banner-dark-1400x400.png">
    <source media="(prefers-color-scheme: light)" srcset="design/github/readme-banner-light-1400x400.png">
    <img alt="switchdeck" src="design/github/readme-banner-dark-1400x400.png" width="680">
  </picture>
</p>

<h1 align="center">switchdeck</h1>

<p align="center"><b>A macOS menu bar switcher for multiple Claude Code accounts, with an optional OpenAI Codex usage row and launcher.</b></p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS-2D647F?style=flat-square">
  <img alt="Status" src="https://img.shields.io/badge/status-v1.5-2D647F?style=flat-square">
  <img alt="Local only" src="https://img.shields.io/badge/local-only-2D647F?style=flat-square">
  <img alt="Stack" src="https://img.shields.io/badge/built%20with-Python-1A1917?style=flat-square">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-1A1917?style=flat-square"></a>
</p>

## What it does

- Switches between Claude Code accounts from the menu bar in one click.
- Shows 5 hour and 7 day usage for every account without opening a terminal.
- Logs every switch locally, so usage is measured rather than remembered.
- Makes zero network calls in a stock install: everything is read from local files and the local cswap engine.
- Optional, off by default: a Codex token/cost row (read-only, via ccusage) that also launches Codex in a terminal. Enabling it opts into network calls to npm; see Configuration.

## Features

### Switching

- **One row per account slot,** showing 5h and 7d usage inline.
- **One click to switch.** The credential swap is delegated to the engine, never reimplemented.
- **Identity-keyed slots.** Two accounts on the same email hold separate slots, verified.
- **Round-trip verified.** Config updates instantly; a running session picks up the change in about 30 seconds or on restart.
- **MCP connectors survive switching.** Connected claude.ai connectors do not require re-authentication.

### Usage

- **Claude quota windows** read from the engine's JSON output, with a staleness marker when the engine serves a cached last-good value.
- **Engine contract.** The validated cswap version and JSON schema are pinned; drift shows a warning row instead of failing silently.
- **Refresh on demand.** The manual Refresh also refreshes Codex when that row is enabled; the automatic timer never does.
- **Codex row (opt-in, off by default).** Token and cost via ccusage; clicking it launches Codex in a terminal. Claude and Codex credentials coexist, so switching tools is a launch, not a credential swap.

### Auto-switch narration (dry-run, on by default)

- Each refresh tick asks the engine what its auto-switch mode **would** do (`cswap auto --once --dry-run --json`) and narrates the answer. Nothing is ever switched.
- A notification like "Would switch slot 2 to slot 1, 5h at 91%" means the engine's threshold logic would have moved you right then. It fires once per distinct condition and repeats only after the condition clears and returns.
- Every narrated event also lands in the local click log, so a week of notifications can be reviewed before trusting the real thing.
- Real auto-switching stays off. It is the engine's feature, not this app's; enabling it is a deliberate engine-side decision (`cswap auto`), and its thresholds, cooldown, and strategy are engine config that this app neither reads nor sets.
- Set `AUTO_NARRATE = False` in `local_settings.py` to silence narration entirely.

### Operations

- **LaunchAgent for run at login.**
- **Local click log,** so behaviour gates are measured against real usage.
- **Gitignored labels.** Account names come from `local_settings.py`; committed code ships generic names.

## Stack

- App: Python, rumps menu bar app
- Credential engine: [claude-swap (cswap)](https://github.com/realiti4/claude-swap), installed via `uv tool install claude-swap`, validated version pinned in `switchbar.py`
- Codex usage (opt-in): ccusage
- Autostart: macOS LaunchAgent

## Install

Requires: macOS, Python 3.11 or later, `uv`.

```bash
git clone https://github.com/ShashankKarpal/switchdeck.git
cd switchdeck
uv tool install claude-swap
python3 -m venv ~/.switchdeck-venv && ~/.switchdeck-venv/bin/pip install rumps
cp local_settings.example.py local_settings.py
cp com.shashank.switchbar.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.shashank.switchbar.plist
```

The venv lives at `~/.switchdeck-venv`, which is where the LaunchAgent expects it. Edit the plist before loading it: replace `YOU` with your macOS username and point the two `switchdeck` paths at wherever you cloned the repo.

## Configuration

Copy `local_settings.example.py` to `local_settings.py` and fill it in. `local_settings.py` is gitignored and never committed.

```python
SLOT_LABELS = {1: "primary", 2: "secondary"}   # menu row names
SHORT_LABELS = {1: "1", 2: "2"}                # menu bar title suffix
# CSWAP_BIN = "/Users/YOU/.local/bin/cswap"
# REFRESH_SECONDS = 300
# CODEX_REFRESH_SECONDS = 1800
# AUTO_NARRATE = False   # dry-run auto-switch narration is on by default
# Codex row is off by default (no network calls in a stock install). Enable:
# CODEX_USAGE_CMD = ["npx", "-y", "ccusage@latest", "codex", "--json"]
# CODEX_LAUNCH_CMD = ["open", "-na", "Terminal", "--args", "-e", "codex"]  # default launcher is Ghostty; set your own terminal here
```

Real account labels stay in the local copy only. Nothing in this repository identifies an account.

## Usage

Click the menu bar item. Each account row shows usage and switches on click. With the opt-in Codex row enabled, it shows usage and opens a terminal running Codex, and Refresh updates both.

## Project structure

```
switchbar.py                    the rumps menu bar app
local_settings.example.py       label and path placeholders
com.shashank.switchbar.plist    LaunchAgent for run at login
design/                         brand assets, tokens, BRAND.md
ROADMAP.md                      behavior gates per version
CLAUDE.md                       decision log, deliberately public
```

## Design principle

Own the UI, wrap the engine. The dangerous part, swapping live OAuth credentials, is delegated to a maintained tool rather than reimplemented. Only the menu bar surface is owned here, so engines upgrade as dependencies.

## Roadmap

Every version must prove one human behavior changed, not that a feature shipped. Full gates in [ROADMAP.md](ROADMAP.md).

| Version | Behavior to prove | Status |
|---|---|---|
| v0 | Engine validated, round-trip switching works | Shipped |
| v1.5 | Menu bar switcher and Codex usage row | Shipped |
| v2+ | Superseded: [docs/redteam-audit-2026-08-17.md](docs/redteam-audit-2026-08-17.md) is the decided plan | Superseded |

One gate exception has been taken and is logged with its reason in [CLAUDE.md](CLAUDE.md).

## Credits

[claude-swap](https://github.com/realiti4/claude-swap) by realiti4 does the credential work. ccusage provides Codex figures. This repository is the UI and the discipline around it.

## License

MIT. See [LICENSE](LICENSE).

## Author

Built by Shashank Karpal.

> Designed and built with Claude (Anthropic).
