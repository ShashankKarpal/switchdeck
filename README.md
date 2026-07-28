<!-- BANNER: uncomment once design/github/readme-banner-{light,dark}-1400x400.png exist.
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)"  srcset="design/github/readme-banner-dark-1400x400.png">
    <source media="(prefers-color-scheme: light)" srcset="design/github/readme-banner-light-1400x400.png">
    <img alt="switchdeck" src="design/github/readme-banner-dark-1400x400.png" width="680">
  </picture>
</p>
-->

<h1 align="center">switchdeck</h1>

<p align="center"><b>A macOS menu bar switcher and usage deck for running multiple Claude Code accounts and OpenAI Codex.</b></p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS-0F7D74?style=flat-square">
  <img alt="Status" src="https://img.shields.io/badge/status-v1.5-0F7D74?style=flat-square">
  <img alt="Local only" src="https://img.shields.io/badge/local-only-0F7D74?style=flat-square">
  <img alt="Stack" src="https://img.shields.io/badge/built%20with-Python-1C1B1D?style=flat-square">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-1C1B1D?style=flat-square"></a>
</p>

## What it does

- Switches between Claude Code accounts from the menu bar in one click.
- Shows 5 hour and 7 day usage for every account without opening a terminal.
- Shows Codex token usage and cost in the same place.
- Launches Codex in a terminal from the same menu.
- Logs every switch locally, so usage is measured rather than remembered.

## Features

### Switching

- **One row per account slot,** showing 5h and 7d usage inline.
- **One click to switch.** The credential swap is delegated to the engine, never reimplemented.
- **Identity-keyed slots.** Two accounts on the same email hold separate slots, verified.
- **Round-trip verified.** Config updates instantly; a running session picks up the change in about 30 seconds or on restart.
- **MCP connectors survive switching.** Connected claude.ai connectors do not require re-authentication.

### Usage

- **Claude quota windows** read from the engine's JSON output.
- **Codex token and cost** read from ccusage.
- **Refresh on demand,** which refreshes both Claude and Codex.
- **Codex row launches the tool.** Claude and Codex credentials coexist, so switching tools is a launch, not a credential swap.

### Operations

- **LaunchAgent for run at login.**
- **Local click log,** so behaviour gates are measured against real usage.
- **Gitignored labels.** Account names come from `local_settings.py`; committed code ships generic names.

## Stack

- App: Python, rumps menu bar app
- Credential engine: [claude-swap (cswap)](https://github.com/realiti4/claude-swap), installed via `uv tool install claude-swap`
- Codex usage: ccusage
- Autostart: macOS LaunchAgent

## Install

Requires: macOS, Python 3.11 or later, `uv`.

```bash
git clone https://github.com/ShashankKarpal/switchdeck.git
cd switchdeck
uv tool install claude-swap
python3 -m venv .switchdeck-venv && .switchdeck-venv/bin/pip install rumps
cp local_settings.example.py local_settings.py
cp com.shashank.switchbar.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.shashank.switchbar.plist
```

Edit the plist paths to match your own home directory before loading it.

## Configuration

Copy `local_settings.example.py` to `local_settings.py` and fill it in. `local_settings.py` is gitignored and never committed.

```python
SLOT_LABELS = {1: "primary", 2: "secondary"}   # menu row names
SHORT_LABELS = {1: "1", 2: "2"}                # menu bar title suffix
# CSWAP_BIN = "/Users/YOU/.local/bin/cswap"
# REFRESH_SECONDS = 300
# CODEX_REFRESH_SECONDS = 1800
# CODEX_USAGE_CMD = None   # disable the Codex row
```

Real account labels stay in the local copy only. Nothing in this repository identifies an account.

## Usage

Click the menu bar item. Each account row shows usage and switches on click. The Codex row shows usage and opens a terminal running Codex. Refresh updates both.

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
| v2 | Codex quota windows, desktop widget, auto-switch | Gated |

One gate exception has been taken and is logged with its reason in [CLAUDE.md](CLAUDE.md).

## Credits

[claude-swap](https://github.com/realiti4/claude-swap) by realiti4 does the credential work. ccusage provides Codex figures. This repository is the UI and the discipline around it.

## License

MIT. See [LICENSE](LICENSE).

## Author

Built by Shashank Karpal.

> Designed and built with Claude (Anthropic).
