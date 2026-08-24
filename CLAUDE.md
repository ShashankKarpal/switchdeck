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

## 2026-08-17: engine revalidated on claude-swap 0.25.0, contract pinned
- Upgraded 0.19.0 to 0.25.0 (uv tool upgrade) after a `cswap export` safety backup (gitignored). Revalidation PASSED: round-trip switch verified both directions against the org identity in ~/.claude.json; same-email slots held distinct org identities; MCP config in ~/.claude.json survived the cycle byte-identical.
- JSON contract: every 0.25.x payload carries schemaVersion (integer 1), pinned in switchbar.py as VALIDATED_SCHEMA_VERSION beside VALIDATED_ENGINE; drift renders one non-clickable warning row and changes nothing else. Shape change vs 0.19.0: when the live usage fetch fails, `usage` is null and the last success moves to `lastGoodUsage` with `usageStatus` and `lastGoodAgeSeconds`. Ruling (Shanky, 2026-08-17): fall back to lastGoodUsage with a staleness marker and surface a non-ok usageStatus inline, rather than degrading to "usage n/a".
- Pre-existing finding, not caused by the upgrade: slot 1 reported usageStatus relogin_required with lastGoodUsage about 14 days stale, so its usage fetching has been failing since about 2026-08-03 while credential switching kept working throughout. Re-login is an owner action outside the app.
- Upstream boundary restated: 0.25.x ships its own menu bar app and auto-switch. Per docs/redteam-audit-2026-08-17.md, this app narrates the engine and never reimplements thresholds or switching logic.

## 2026-08-24: v1.9, notification delivery proven, resume card, rename completed
- Audit item 4's prerequisite RESOLVED, negatively: a rumps notification does NOT render from this unbundled app on macOS Tahoe 26.6.2. rumps reads an Info.plist beside sys.executable for CFBundleIdentifier; a venv has none, so the notification centre is nil and every call raised into the old bare `except: pass`. Tested both as a bare script and inside a live rumps run loop. This means no notification this app ever fired was delivered, on any version.
- Ruling: fix delivery without bundling. The app writes the two-key Info.plist next to the interpreter at startup (idempotent, because the file lives in the venv and a venv rebuild removes it), falls back to `osascript display notification` when the centre is still unreachable, and writes every notification failure to the click log. Bundling stays deferred to the Swift rewrite per the audit; the menu bar template icon stays unwired for the same reason.
- Rule adopted: best-effort side effects must leave evidence on failure. A swallowed exception around a notification is how a feature stays absent for a year with no signal.
- Audit item 4 (resume card) SHIPPED now that delivery is real: a successful switch names the target slot, the verified active org, the live CLI session count, and the last project (basename of the most recent `projects` entry in ~/.claude.json, HOME excluded; lastStartTime is epoch millis, coerced defensively). Degrades clause by clause.
- Audit item 5 (rename completion) SHIPPED: switchbar.py to switchdeck.py, class SwitchBar to SwitchDeck, notification titles to SwitchDeck, LaunchAgent label com.shashank.switchbar to com.shashank.switchdeck (installer boots out the old label and retires its plist), stale ~/Documents/GitHub paths corrected in the tracked plist and README.
- Interpreter ruling: this app is pinned to a uv-managed CPython, never a Homebrew one. The venv was built on Homebrew python@3.14, that formula was removed during the uv migration, and the LaunchAgent then failed to spawn with exit 78 EX_CONFIG for three days in silence. Homebrew python@3.14 was deliberately NOT reinstalled: reviving it would restore exactly the dependency that broke. See docs/STATE.md for the incident.
- scripts/install.sh added because the audit's "cannot survive a venv deletion" finding was the root cause of the outage, and because a hand-built venv never gets the Info.plist. scripts/selftest_notify.py added to fail non-zero when the notification centre cannot be reached.

## Security and hygiene rules (every agent session)

1. Never commit secrets: no API keys, tokens, passwords, private keys, or .env files. Templates belong in *.example files with placeholder values only.
2. Untracking or deleting a file does not remove it from git history. If a secret ever lands in a commit: rotate it at the provider first, then rewrite history with git filter-repo.
3. At the end of each session: delete unused code, merge duplicate helpers, remove commented-out blocks. Use deterministic tools (linters, dead-code finders) and review the diff before deleting.
4. Keep .gitignore covering .env, .env.*, and secrets.* (with !*.example exemptions). Never weaken it.
5. The gitleaks CI workflow (.github/workflows/gitleaks.yml) stays. Never remove or bypass it.
