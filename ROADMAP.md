# Roadmap (behavior-gated)

Each version ships only after the previous version's behavior signal is proven. One logged exception below.

## v0: validation, no build (PASSED technical checks)
- Engine installed, both accounts vaulted in slots, round-trip switch verified.
- Behavior to prove: reaching for the engine instead of the browser login dance.
- Status: observation window superseded by the v1.5 exception; the habit signal now measures menu bar use instead.

## v1.5: the switch plus usage, minimal menu bar UI (SHIPPED under logged gate exception)
- rumps menu bar app: one row per account slot from a gitignored local map, one click calls the engine, checkmark on the active slot, post-switch verification against the active org.
- Per-account 5h/7d usage inline (engine JSON), read-only Codex token/cost row (ccusage).
- Local click log so the gate is measured, not remembered.
- Behavior to prove: switching from the menu bar mid-session during real work.
- Signal: 3+ menu bar switches per week for 2 consecutive weeks, excluding the first 2 days of test clicks.

## v2: unified view, completed
- Uebersicht desktop widget fed by the same JSON sources.
- Codex quota windows (5h/weekly bars, not just token cost); requires reading the local Codex auth session, evaluate ccusage/CodexBar-style approaches first.
- Behavior to prove: checking headroom before token-heavy work, front-loading before the evening compression peak.
- Signal: on 4 of 5 weekdays, first heavy session starts before 17:00 local, measured from usage data over 2 weeks.

## v3: proactive
- Threshold auto-switch via the engine's auto mode (dry-run week first), launchd-managed, with a notification on each intervention.
- Behavior to prove: no more hard-limit lockouts mid-session.
- Signal: zero lockouts across 2 weeks, cross-checked against the auto-switch log.

## Future candidates (only if earlier behaviors stick)
- Quick model toggle in the same menu.
- Cross-machine usage rollup over Tailscale.
- Usage folded into an existing daily brief.
- Codex account switching, if and only if a second Codex account exists (the switch layer is already generic; this is a provider addition, not a rewrite).
- Packaging: Login Item, LSUIElement, code signing decision.
