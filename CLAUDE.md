# Decision log

## 2026-07-07: v0 engine decision and validation
- Engine: claude-swap (cswap) via uv tool install. Alternatives skipped: menu bar switchers that are themselves UIs (violates own-the-UI principle) or that key account backups by email (collapses same-email accounts).
- Go/no-go PASSED: two accounts on the same email held in separate numbered slots, keyed by account identity.
- Round-trip switch verified both directions. Config updates instantly; a running session picks up the change in about 30 seconds (Keychain cache) or on restart.
- MCP finding: connected claude.ai connectors survived switch cycles without re-authentication.
- Observation window opened: gate was 4+ real switches in 7 days, zero browser re-logins.

## 2026-07-07 (later): v0 gate override, v1.5 built early
- Gate override: the menu bar switcher plus Codex usage row was built before the v0 observation window completed. Reason: a model availability window closing the same day; declared a one-time exception. Logged per protocol.
- Scope shipped: SwitchBar rumps app (engine-backed switching, per-account 5h/7d usage, read-only Codex token/cost row), LaunchAgent, gitignored local labels, local click log.
- Held back despite the exception: Codex account switching (single account, behavior unprovable, would be dead code), the desktop widget, and auto-switch.
- Adjusted gate: the v0 CLI-habit gate is retired; the active gate is v1.5's signal (3+ menu bar switches per week for 2 consecutive weeks, first 2 days excluded). Nothing further ships until it passes.
- Codex caveat: ccusage reports token/cost from local logs, not ChatGPT quota windows; quota bars are a v2 item.
- Codex row semantics: clicking it launches Codex in the terminal (tool jump). Claude and Codex are separate tools with coexisting credentials, so Claude-to-Codex is not a credential switch; account-level Codex switching remains gated on a second Codex account existing.
