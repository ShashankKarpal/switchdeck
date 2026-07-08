# switchdeck

A macOS menu bar switcher and usage deck for people running multiple Claude Code accounts, built behavior-first.

## What this is

I run two Claude Code accounts (primary and secondary) plus OpenAI Codex. Switching accounts natively means logout, browser OAuth, and a broken flow. This project puts a one-click switch and a unified usage view in the macOS menu bar, without forking anything.

## Architecture principle: own the UI, wrap the engine

The dangerous part (swapping live OAuth credentials) is delegated to a maintained tool, not reimplemented:

- Engine: [claude-swap (cswap)](https://github.com/realiti4/claude-swap), installed as a dependency via `uv tool install claude-swap`. It vaults each account in a numbered slot and swaps the active credential safely. Verified: it keys accounts by identity, so two accounts on the same email hold separate slots.
- Usage data: cswap's JSON output for Claude account quota windows; ccusage for Codex token and cost figures.
- Owned surfaces only: a thin Python menu bar app (rumps) and, later, an Uebersicht desktop widget. Nothing forked, engines upgraded as dependencies.

## The app (SwitchBar)

`switchbar.py` is a small rumps menu bar app:

- One row per Claude account slot, showing 5h and 7d usage, one click to switch (calls the engine).
- A Codex row: shows usage, and one click jumps into the tool (opens a terminal running Codex). Claude and Codex credentials coexist, so tool switching is a launch, not a credential swap. Account-level Codex switching becomes a small addition if a second Codex account ever exists.
- Labels come from a gitignored `local_settings.py` (see `local_settings.example.py`); nothing identifying is committed.
- Every menu bar switch is logged locally, so behavior gates are measured, not remembered.

Run at login via the included LaunchAgent plist.

## Behavior-first development

Every version must prove a specific human behavior changed, not just that a feature shipped. Each version names one behavior and an observable signal, and the next version is gated on it. See ROADMAP.md. One gate exception has been taken and is logged with its reason in CLAUDE.md; the measurement discipline continues regardless.

## Credits

claude-swap by realiti4 does the heavy lifting. ccusage provides Codex figures. This repo is the UI and the discipline around it.
