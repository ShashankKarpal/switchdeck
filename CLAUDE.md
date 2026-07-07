# Decision log

## 2026-07-07: v0 engine decision and validation
- Engine: claude-swap (cswap) via uv tool install. Alternatives skipped: menu bar switchers that are themselves UIs (violates own-the-UI principle) or that key account backups by email (collapses same-email accounts).
- Go/no-go PASSED: two accounts on the same email held in separate numbered slots, keyed by account identity.
- Round-trip switch verified both directions. Config updates instantly; a running session picks up the change in about 30 seconds (Keychain cache) or on restart.
- MCP finding: connected claude.ai connectors survived switch cycles without re-authentication.
- Observation window opened: gate is 4+ real switches in 7 days, zero browser re-logins, plus one trial of session mode.
