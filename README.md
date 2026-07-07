# switchdeck

A macOS menu bar switcher and usage deck for people running multiple Claude Code accounts, built behavior-first.

## What this is

I run two Claude Code accounts (primary and secondary) plus OpenAI Codex. Switching accounts natively means logout, browser OAuth, and a broken flow. This project puts a one-click switch and a unified usage view in the macOS menu bar, without forking anything.

## Architecture principle: own the UI, wrap the engine

The dangerous part (swapping live OAuth credentials) is delegated to a maintained tool, not reimplemented:

- Engine: [claude-swap (cswap)](https://github.com/realiti4/claude-swap), installed as a dependency via `uv tool install claude-swap`. It vaults each account in a numbered slot and swaps the active credential safely. Verified: it keys accounts by identity, so two accounts on the same email hold separate slots.
- Usage data: cswap's own usage view for Claude accounts; ccusage planned for the unified view including Codex.
- Owned surfaces only: a thin Python menu bar app (rumps) and an Übersicht desktop widget. Nothing forked, engines upgraded as dependencies.

## Behavior-first development

Every version must prove a specific human behavior changed, not just that a feature shipped. Each version names one behavior and an observable signal, and the next version is gated on it. See ROADMAP.md.

## Status

v0 (validation) passed its technical checks: both same-email accounts vaulted in separate slots, round-trip switching verified. Currently in the v0 observation window proving the switching habit before any UI is built.

## Codex note

One Codex account means switching it is a no-op, so Codex appears only in the usage view. If a second Codex account ever exists, switching gets promoted.

## Credits

claude-swap by realiti4 does the heavy lifting. This repo is the UI and the discipline around it.
