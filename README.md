<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)"  srcset="design/github/readme-banner-dark-1400x400.png">
    <source media="(prefers-color-scheme: light)" srcset="design/github/readme-banner-light-1400x400.png">
    <img alt="switchdeck" src="design/github/readme-banner-dark-1400x400.png" width="680">
  </picture>
</p>

<h1 align="center">switchdeck</h1>

<p align="center"><b>A macOS menu bar deck for two Claude accounts: switch the CLI login in one click, see every quota window with its reset time and pace, open a separate Claude Desktop per account, and know when a switch is safe.</b></p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS-2D647F?style=flat-square">
  <img alt="Status" src="https://img.shields.io/badge/status-v2.0-2D647F?style=flat-square">
  <img alt="Local only" src="https://img.shields.io/badge/local-only-2D647F?style=flat-square">
  <img alt="Stack" src="https://img.shields.io/badge/built%20with-Python-1A1917?style=flat-square">
  <img alt="Tests" src="https://img.shields.io/badge/tests-51%20unittest-1A1917?style=flat-square">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-1A1917?style=flat-square"></a>
</p>

## What it does

- **Switches Claude Code accounts from the menu bar in one click.** Two accounts on the same email hold separate, identity-keyed slots; the credential swap is delegated to the [claude-swap](https://github.com/realiti4/claude-swap) engine, never reimplemented.
- **Shows every quota window per account, inline.** 5 hour, 7 day and any per-model weekly window the engine reports (a Fable window, for example), the reset time of the tightest window, and a one-word pace verdict: on pace, ahead of pace, will cap early.
- **Keeps headroom in the menu bar title.** `⇄ kk2 45%` is the active account and its tightest window, readable without opening the menu.
- **Knows when a switch is safe.** Counts running Claude Code CLI sessions and says whether any is busy right now, because a switch reaches a running session only after its ~30 second credential cache expires and never mid-reply.
- **Opens a separate Claude Desktop per account.** Optional launcher apps put two desktop Claudes side by side, each on its own profile, without touching the app itself.
- **Narrates what auto-switch would do, without doing it.** Dry-run only; the engine owns thresholds and the decision to ever turn it on is yours, at the engine.
- **Makes no network calls of its own.** Everything is read from local files and the local engine. The engine fetches usage from Anthropic with your stored login on each refresh; that is the one network path in a stock install. The optional Codex row (off by default) adds npm.

## Features

### Switching

- **One row per account slot,** showing usage inline, with a checkmark on the active one.
- **One click to switch.** The engine swaps the credential; the app verifies the active organization afterwards and shows a resume card: which account is now active, how many CLI sessions are live and whether they are busy, and the last project you were in.
- **Identity-keyed slots.** Two accounts on the same email hold separate slots, verified against the organization identity.
- **MCP connectors survive switching.** Connected claude.ai connectors do not require re-authentication.
- **Live session awareness.** "2 live CLI session(s), 1 busy: switch applies in ~30s, not mid-reply." Busy means the session's transcript file changed in the last 10 seconds, checked by file time only; the app never opens a transcript.

### Usage

- **Every window the engine reports,** in a fixed order: 5h, 7d, per-model weekly windows under their own name, spend limit when present. Rows never reorder between refreshes.
- **Reset time and pace, from the engine.** The tightest window shows the engine's reset clock inline ("Fable 45% (resets Sep 7 17:30)") and a pace chip summarizes the engine's weekly verdicts. Nothing is recomputed here.
- **Honest freshness.** A staleness marker when the engine serves a cached last-good value, and an age marker when the served number is more than five minutes old, so a stalled poll cannot pass for a current reading.
- **Engine contract.** The validated engine version and JSON schema are pinned; drift shows one warning row instead of failing silently.
- **Never blocks the menu.** Engine calls run on a background worker; the menu is rendered from the last finished snapshot, so an offline engine cannot freeze the menu bar.

### Desktop app slots (optional)

- **One Claude Desktop per account, side by side.** `scripts/desktop_slots.py build` installs a small launcher app per slot into `~/Applications` (for example `Claude kk1.app` and `Claude kk2.app`). Each opens Claude Desktop on its own profile folder (`~/Library/Application Support/Claude Slot N`), so you sign into the second account there once and both run at the same time. If that profile is already open, the launcher brings it to the front instead of starting a second copy.
- **Safe by construction.** Launchers are identified by a marker key inside their Info.plist, never by name. The installer refuses to replace any app it did not create and never deletes a profile folder. Launching always goes through `open -n`, which is the one path verified to leave the main Claude profile alone.
- **In the menu.** One "Open Desktop: <label>" row per installed launcher, with "(running)" when that profile is open.
- **Independent of the CLI login.** Claude Code keeps one machine login; the desktop profiles keep their own. Chat history is not shared between profiles, by design. Needs the Xcode command line tools once, to compile the launcher.

### Pending badge (optional)

- Point `BADGE_CMD` at any local command that prints `{"schemaVersion": 1, "accounts": {"<key>": <count>}}`. A count above zero shows " - N pending" on that slot's row and "[N]" in the title for the active slot. Counts only ever cross that boundary; the app never asks for subjects or paths. Off by default.

### Auto-switch narration (dry-run, on by default)

- Each refresh asks the engine what its auto-switch mode **would** do (`cswap auto --once --dry-run --json`) and narrates the answer. Nothing is ever switched.
- A notification like "Would switch slot 2 to slot 1, 5h at 91%" means the engine's threshold logic would have moved you right then. It fires once per distinct condition and repeats only after the condition clears and returns. Every narrated event also lands in the local click log.
- Real auto-switching stays off. It is the engine's feature; enabling it is a deliberate engine-side decision (`cswap auto`), and its thresholds, cooldown and strategy are engine config this app neither reads nor sets. Set `AUTO_NARRATE = False` to silence narration.

### Operations

- **LaunchAgent for run at login,** from a real signed app bundle, so notification banners actually present.
- **Local click log** (mode 0600), so behaviour gates are measured against real usage.
- **Gitignored labels and commands.** Account names, the badge command and the Codex launcher live in `local_settings.py`; committed code ships generic names and names no tool.
- **Unit tests** for every formatting, contract and parsing function (`tests/`, 51 cases).

## Stack

- App: Python, [rumps](https://github.com/jaredks/rumps) menu bar app, run from a minimal signed `.app` bundle
- Credential engine: [claude-swap (cswap)](https://github.com/realiti4/claude-swap), installed via `uv tool install claude-swap`, validated version pinned in `switchdeck.py`
- Desktop slot launchers: a 40-line Swift program compiled at install time
- Codex usage (opt-in): ccusage
- Autostart: macOS LaunchAgent

## Install

Requires: macOS, `uv`. For the optional Desktop app slots, the Xcode command line tools.

```bash
git clone https://github.com/ShashankKarpal/switchdeck.git
cd switchdeck
scripts/install.sh
```

That installs the engine, builds the package venv at `~/.switchdeck-venv` against a uv-managed Python, builds `~/Applications/SwitchDeck.app` (a minimal signed bundle whose executable is a copy of that same static CPython, with the brand icon), renders the LaunchAgent with your real paths, boots it, and fails loudly if the app did not come up. Re-run it any time to repair an install; add `--rebuild` to recreate the venv from scratch. On first run macOS asks to allow SwitchDeck notifications; the answer is recorded in the click log.

Then edit `local_settings.py` (created for you on first run) to set your account labels.

Optional, for a second Claude Desktop per account:

```bash
scripts/desktop_slots.py build     # one launcher app per slot into ~/Applications
scripts/desktop_slots.py status    # what is installed, what is running
scripts/desktop_slots.py remove    # deletes the launchers it made; profiles stay
```

Why a bundle: macOS only registers notification identities for real, LaunchServices-registered app bundles. An unbundled interpreter can call the notification APIs successfully while the system files every banner into Notification Center without presenting one, which is exactly what happened here for a year. The bundle also gives the process a real name in the menu bar layout tools instead of `python3`.

Why a script rather than a copied plist: the venv is outside the repo and depends on an interpreter that a package manager can remove underneath it. When that happened here, launchd failed to spawn with exit code 78 and, because a menu bar app has no window to miss, nothing announced it. The script rebuilds every piece a hand install gets wrong, and proves the result is running before it reports success.

## Configuration

Copy `local_settings.example.py` to `local_settings.py` and fill it in. `local_settings.py` is gitignored and never committed.

```python
SLOT_LABELS = {1: "primary", 2: "secondary"}   # menu row names
SHORT_LABELS = {1: "1", 2: "2"}                # menu bar title suffix, also the Desktop launcher names
# CSWAP_BIN = "/Users/YOU/.local/bin/cswap"
# REFRESH_SECONDS = 300
# AUTO_NARRATE = False     # dry-run auto-switch narration is on by default
# TITLE_USAGE = False      # the title shows the active slot's tightest window percent by default
# BADGE_CMD = ["/usr/bin/python3", "/path/to/your/badge-command", "--json"]   # pending badge, off by default
# BADGE_SLOT_KEYS = {1: "work", 2: "personal"}                                # slot to key in the badge JSON
# Codex row is off by default (no network calls in a stock install). Enable:
# CODEX_USAGE_CMD = ["npx", "-y", "ccusage@latest", "codex", "--json"]
# CODEX_LAUNCH_CMD = ["open", "-na", "Terminal", "--args", "-e", "codex"]  # default launcher is Ghostty
```

Real account labels stay in the local copy only. Nothing in this repository identifies an account.

## Usage

Click the menu bar item. Each account row shows usage, reset time and pace, and switches on click. Below the rows: the active organization, the live CLI session line, and one "Open Desktop" row per installed launcher. Refresh re-reads everything; with the opt-in Codex row enabled it refreshes Codex too.

## Project structure

```
switchdeck.py                   the rumps menu bar app
desktop_slots.py                Desktop app slot shims: plist, marker, running detection
scripts/install.sh              install or repair, idempotent (bundle, LaunchAgent, venv)
scripts/desktop_slots.py        build, status, remove the Desktop app slot launchers
scripts/selftest_notify.py      notification delivery self-test
tests/                          unit tests (run: ~/.switchdeck-venv/bin/python -m unittest discover -s tests)
local_settings.example.py       label, badge and path placeholders
docs/                           the 2026-08-17 red-team audit that set the current plan
com.shashank.switchdeck.plist   LaunchAgent template for run at login
design/                         brand assets, tokens, BRAND.md
ROADMAP.md                      behavior gates per version (historical)
CLAUDE.md                       decision log, deliberately public
```

## Design principle

Own the UI, wrap the engine. The dangerous part, swapping live OAuth credentials, is delegated to a maintained tool rather than reimplemented. Only the menu bar surface is owned here, so engines upgrade as dependencies. The same rule shapes every later feature: reset times and pace are the engine's own fields, never recomputed; Desktop slots launch the real Claude app rather than copying it; the pending badge reads counts from a command you choose.

## Roadmap

Every version must prove one human behavior changed, not that a feature shipped. Full gates in [ROADMAP.md](ROADMAP.md); the decided plan since 2026-08-17 is [docs/redteam-audit-2026-08-17.md](docs/redteam-audit-2026-08-17.md), and every decision since is in [CLAUDE.md](CLAUDE.md).

| Version | What it proved or shipped | Status |
|---|---|---|
| v0 | Engine validated, round-trip switching works | Shipped |
| v1.5 | Menu bar switcher and Codex usage row | Shipped |
| v1.7 to v1.9.1 | Engine contract, dry-run narration, real notifications from a signed bundle, resume card | Shipped |
| v2.0 | Worker-thread refresh, reset time and pace per window, busy or idle sessions, title headroom, Desktop app slots, pending badge, unit tests | Shipped |
| next | Swift MenuBarExtra rewrite (the long horizon; Python is interim by decision) | Planned |

One gate exception has been taken and is logged with its reason in [CLAUDE.md](CLAUDE.md).

## Credits

[claude-swap](https://github.com/realiti4/claude-swap) by realiti4 does the credential work. The Desktop slot approach follows the marker-and-profile rules worked out by [claude-graft](https://github.com/aaditya-v-more/claude-graft). ccusage provides Codex figures. This repository is the UI and the discipline around it.

## License

MIT. See [LICENSE](LICENSE).

## Author

Built by Shashank Karpal.

> Designed and built with Claude (Anthropic).
