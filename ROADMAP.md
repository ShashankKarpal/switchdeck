# Roadmap (behavior-gated)

Each version ships only after the previous version's behavior signal is proven.

## v0: validation, no build (current)
- Engine installed, both accounts vaulted in slots, round-trip switch verified.
- Behavior to prove: reaching for `cswap` instead of the browser login dance.
- Signal: 4+ real switches in 7 days via a logging wrapper, zero browser re-logins.
- Also under trial: `cswap run` session mode (two accounts in parallel terminals), which may reshape v1.

## v1: the switch, minimal menu bar UI
- rumps menu bar app: two rows (primary, secondary) labeled from a gitignored local slot map, one click calls `cswap switch-to <slot>`, active account shown with a checkmark, post-switch verification by reading the active org from ~/.claude.json.
- Reserved third row: Codex usage (read-only, arrives in v2).
- Local click log (gitignored) so the gate is measured, not remembered.
- Behavior to prove: switching from the menu bar mid-session during real work.
- Signal: 3+ menu bar switches per week for 2 consecutive weeks, excluding the first 2 days of test clicks.

## v2: unified view
- Same menu shows usage bars and reset countdowns for both Claude accounts and Codex (ccusage JSON).
- Übersicht desktop widget fed by the same data.
- Behavior to prove: checking headroom before token-heavy work, front-loading before the evening compression peak.
- Signal: on 4 of 5 weekdays, first heavy session starts before 17:00 local, measured from usage data over 2 weeks.

## v3: proactive
- Threshold auto-switch via the engine's auto mode (dry-run week first), launchd-managed, with a macOS notification on each intervention.
- Behavior to prove: no more hard-limit lockouts mid-session.
- Signal: zero lockouts across 2 weeks, cross-checked against the auto-switch log.

## Future candidates (only if earlier behaviors stick)
- Quick model toggle in the same menu.
- Cross-machine usage rollup over Tailscale.
- Usage folded into an existing daily brief.
- Codex account switching, if and only if a second Codex account exists.
- Packaging: Login Item, LSUIElement, code signing decision.
