# SwitchDeck red team audit, 2026-08-17

Run by the owner's secondary Claude account, Claude Code, read-only. Every claim carries a confidence label: VERIFIED (read in a file or command output), INFERRED (reasoned from evidence), UNVERIFIED (cannot confirm). No repo state was mutated.

## 0. Session continuity brief

Redacted from the public copy: the cross-account continuity brief (inbox state, prior handoffs, backup health, account attribution) contains private infrastructure detail and lives in the owner's private handoff system. Two findings from it that this audit relies on: this project had no continuity handoff before this run, and prior work is split across the owner's two Claude accounts (the build on one, the repo audits on the other).

## 1. Naming and repo authority resolution

**The task premise is wrong on the lineage, and that matters.** There is no cswap repo and never was one under this root. "cswap" is the upstream credential engine, claude-swap by realiti4, installed via `uv tool install claude-swap` (README.md:55, `~/.local/bin/cswap` symlink into uv tools, VERIFIED). It is a dependency, not a former name of this project.

The actual lineage:

| Name | What it is | Evidence |
|---|---|---|
| cswap / claude-swap | Upstream engine dependency, never this project | README.md:55, CLAUDE.md:4, VERIFIED |
| SwitchBar | Internal app name: file, class, plist label, notification titles | switchbar.py:2, :169, :231; com.shashank.switchbar.plist:5, VERIFIED |
| switchdeck | Repo, remote, brand ("the Deck", 2026-07-28) | commit 622fd1d, design/BRAND.md:3, origin URL, VERIFIED |

Authoritative repo path: `switchdeck/` under the owner's projects root. The only match at depth 3; no competing folder. VERIFIED (recursive find, node_modules/.build/dist/vendor pruned).

**Rename pivot status: incomplete in code.** The Deck brand landed in assets and README on 2026-07-28 (622fd1d), but the code still says SwitchBar everywhere: `switchbar.py` filename, `class SwitchBar` (switchbar.py:169), LaunchAgent label `com.shashank.switchbar` (plist:5), notification titles "SwitchBar" (switchbar.py:231, :235, :238). The docstring itself hedges: "SwitchBar (switchdeck v1.6)" (switchbar.py:2). A portfolio app that cannot decide its own name in its own process list is a finding, not a quirk. VERIFIED.

**Second premise correction.** The task frames SwitchDeck as a general app-switching and context-recovery tool. It is not. It is a Claude Code multi-account switcher with usage readouts. The resume-cost frame still applies, but the "context" being recovered is quota headroom and account identity, not window state. The audit proceeds on what the repo actually is.

## 2. Repo forensics

| Item | Value | Confidence |
|---|---|---|
| Last commit | `7a81ee9`, 2026-08-03, "ci: gitleaks-action v3 and checkout v6 for Node 24, add workflow_dispatch", Shashank Karpal | VERIFIED |
| Dormancy | 14 days since last commit | VERIFIED |
| Cadence, 90 days | 14 commits, i.e. the entire history: build burst Jul 7-8 (5), hardening plus brand burst Jul 28-30 (6), docs plus CI Aug 1-3 (2), one v1.6 feature commit Jul 30 | VERIFIED |
| Cadence, 12 months | Same 14 commits; the repo is 6 weeks old | VERIFIED |
| Branch | `main` only, level with `origin/main` (7a81ee9), no stale branches | VERIFIED |
| Working tree | Clean; untracked files are all gitignored (local_settings.py, __pycache__, .DS_Store) | VERIFIED |
| Stash | Empty | VERIFIED |
| WIP commits | None; every message is scoped and conventional | VERIFIED |
| TODO/FIXME/HACK/stubs | Zero across .py, .md, .yml, .plist | VERIFIED (grep) |
| History rewrite | 2026-08-02, to normalize commit author identity; the current log is uniform throughout | VERIFIED (log) plus INFERRED (motive, from private audit notes) |
| Engine version installed | claude-swap 0.19.0 (`cswap --version`, `uv tool list`) | VERIFIED |
| Engine version upstream | 0.25.0, released 2026-08-11 (PyPI). Installed engine is six minor versions behind; no pin, no check anywhere in the repo | VERIFIED |

This is a small, disciplined, dormant repo. The hygiene is real: gitleaks CI, hardened .gitignore, gitignored account labels, decision log. The dormancy is also real, and the one thing rotting during it is the unpinned engine underneath.

## 3. Ground-truth state map

| Area | State | Status | Confidence, evidence |
|---|---|---|---|
| Activation path | Menu bar click only, rumps app started by LaunchAgent at login. No hotkey, no keyboard path of any kind | SHIPS TODAY | VERIFIED, switchbar.py:169-215; launchctl shows com.shashank.switchbar running, PID 1109, exit status 0 |
| State capture | Account credentials vaulted in identity-keyed slots by the cswap engine; the app never touches credentials | SHIPS TODAY (delegated by design) | VERIFIED, CLAUDE.md:4-8, README.md:108 |
| State restore | `cswap switch N --json`, success parsed from JSON, active org re-verified from `~/.claude.json`, v1.6 warns when live CLI sessions mean the switch applies in about 30s | SHIPS TODAY | VERIFIED, switchbar.py:217-241, :123-129, :85-107 |
| Persistence | Append-only text click log at `~/switchdeck-clicks.log`; config in gitignored `local_settings.py`; no database, no other state | SHIPS TODAY | VERIFIED, switchbar.py:31, :132-137; log exists, 25 entries, last 2026-08-17 07:21 |
| Permission handling | No Accessibility, no Screen Recording, no Automation, no elevated permission anywhere. Notifications are best-effort and failures are swallowed (switchbar.py:65-69): if notification permission is revoked the app degrades silently, nothing breaks | SHIPS TODAY | VERIFIED |
| Failure: engine missing or broken | Menu shows "cswap unavailable - click to retry"; switch failure raises a notification with stderr excerpt | SHIPS TODAY | VERIFIED, switchbar.py:197-198, :238-239 |
| Failure: engine schema drift | Nothing. No version pin, no validated-version check. Parsing assumes cswap's JSON shape (accounts, activeAccountNumber, fiveHour/sevenDay pct). Installed 0.19.0 against upstream 0.25.0; an `uv tool upgrade` at any time can silently blank the menu | DECLARED ONLY (risk named in docs/STATE.md:38, absent in code) | VERIFIED |
| Codex row | Reads `npx -y ccusage@latest codex --json` on a timer, click launches Codex. Works, but see the defect and the usage evidence below | HALF-BUILT in effect | VERIFIED, switchbar.py:36, :244-269 |

Two defects found in the 277-line source:

1. **The Codex refresh interval is dead config.** `refresh()` is wired to a rumps Timer at REFRESH_SECONDS=300 (switchbar.py:172). rumps passes the timer object as the sender, so the guard `if _sender is not None: self.refresh_codex()` (switchbar.py:181-183) fires on every automatic tick, not only on manual Refresh clicks. Net effect: `npx -y ccusage@latest` runs every 5 minutes, not every 30 as CODEX_REFRESH_SECONDS intends. INFERRED (rumps timer callback semantics from library knowledge; code path VERIFIED). This is also a network call to the npm registry every 5 minutes from an app whose README badge says "local-only". The badge is false as shipped. VERIFIED (switchbar.py:36, README.md:16).
2. **`self.codex_line` is written from a worker thread and read from the main thread with no synchronization** (switchbar.py:245-258, :202). Benign under CPython's GIL for a str assignment, but it is the kind of thing a hostile reviewer circles. VERIFIED.

## 4. The previously decided roadmap, quoted

Source: `ROADMAP.md`, committed 2026-07-07 in c41c49a ("v0 validated: docs, roadmap, decision log"), file last modified 2026-07-08. Decision dates from `CLAUDE.md` decision log entries 2026-07-07. All quotes verbatim. VERIFIED.

| # | Item | Verbatim quote | Source |
|---|---|---|---|
| R1 | v2 desktop widget | "Uebersicht desktop widget fed by the same JSON sources." | ROADMAP.md:18 |
| R2 | v2 Codex quota windows | "Codex quota windows (5h/weekly bars, not just token cost); requires reading the local Codex auth session, evaluate ccusage/CodexBar-style approaches first." | ROADMAP.md:19 |
| R3 | v3 auto-switch | "Threshold auto-switch via the engine's auto mode (dry-run week first), launchd-managed, with a notification on each intervention." | ROADMAP.md:24 |
| R4 | Model toggle | "Quick model toggle in the same menu." | ROADMAP.md:29 |
| R5 | Tailscale rollup | "Cross-machine usage rollup over Tailscale." | ROADMAP.md:30 |
| R6 | Daily brief | "Usage folded into an existing daily brief." | ROADMAP.md:31 |
| R7 | Codex switching | "Codex account switching, if and only if a second Codex account exists (the switch layer is already generic; this is a provider addition, not a rewrite)." | ROADMAP.md:32 |
| R8 | Packaging | "Packaging: Login Item, LSUIElement, code signing decision." | ROADMAP.md:33 |

Rename-implied pivot: none of substance. The Deck brand (2026-07-28, 622fd1d, design/BRAND.md) is a visual identity for the same product, not a scope pivot; and even that shallow pivot never landed in code (Section 1). There was never a Cswap-to-SwitchDeck product pivot because there was never a product named Cswap. VERIFIED.

**The governing constraint the roadmap set for itself, quoted:** "Signal: 3+ menu bar switches per week for 2 consecutive weeks, excluding the first 2 days of test clicks" (ROADMAP.md:15); "Nothing further ships until it passes" (CLAUDE.md:14).

**Gate verdict, evaluated for the first time, from the complete 25-entry click log (VERIFIED):**

| ISO week | Switches (Jul 8-9 test days excluded) | Meets 3+ |
|---|---|---|
| Jul 6-12 | 4 (all Jul 10) | yes |
| Jul 13-19 | 0 | no |
| Jul 20-26 | 0 | no |
| Jul 27-Aug 2 | 4 | yes |
| Aug 3-9 | 2 | no |
| Aug 10-16 | 7 | yes |
| Aug 17- (partial) | 1 | pending |

No two consecutive qualifying weeks exist. **The v1.5 gate has FAILED as written.** By the project's own constitution, every v2 and v3 item is currently illegitimate to build. At the same time the tool is demonstrably in real use: 21 switches across 6 weeks, in bursts that track multi-account workdays, including switches with live CLI sessions attached. The gate measures habit regularity; the user works in bursts. The gate's shape is wrong for the person it measures, and nobody evaluated it for six weeks, which means the governance loop was dead until today. Both facts go to the owner as open question 1.

## 5. Red team pass 1: the old roadmap, item by item

**R1 Uebersicht widget: KILL.** The sibling repo uebersicht-claude-tokens already is this widget; BRAND.md:5 even states switchdeck "shares turquoise with uebersicht-claude-tokens by design". Building a second desktop widget inside switchdeck duplicates the owner's own portfolio, adds a third-party runtime (Uebersicht) as a dependency, and displays nothing the menu bar does not already show. Cross-repo dependency noted per scope guard; the sibling's tree was not read. A widget also has zero system-level polish value: it is a webview pinned to a desktop.

**R2 Codex quota windows: KILL.** Three independent kill shots. First, the click log: 4 "open codex" clicks ever, all on ship day 2026-07-08, zero Codex interactions in the 40 days since (VERIFIED). The feature's own audience does not exist. Second, it requires parsing the local Codex auth session, an undocumented format that breaks on any Codex update, which is exactly the fragile-dependency class this repo's design principle exists to avoid. Third, docs/STATE.md:45 already notes claude-burnrate covers quota visualization on the Claude side. A feature that failed its behavior gate before being built does not get built.

**R3 Auto-switch: REWRITE.** The premise expired. Upstream claude-swap now ships auto-switching itself; the 0.25.0 PyPI description reads "let it switch for you before you hit a rate limit" (VERIFIED, PyPI, 2026-08-11 release). Writing threshold logic in the app would duplicate the engine and violate the repo's own own-the-UI principle (README.md:108). What survives the rewrite: upgrade to and validate against 0.25.x, then surface the engine's auto-switch interventions as notifications and click-log entries. The app narrates; the engine acts.

**R4 Model toggle: KILL.** A menu bar model toggle either rewrites Claude Code's own config file underneath running sessions (fragile, and Claude Code rewrites it back) or sets an environment variable that cannot reach already-running sessions. Claude Code's in-session `/model` already does this correctly at the only moment it matters. This item adds a configuration surface and reduces no resume cost, which fails the design philosophy on both counts.

**R5 Tailscale rollup: KILL.** A cross-machine network service in a repo whose badge says local-only, maintained by one person, for a second machine that runs no interactive Claude work (INFRA.md: code is written on the M4 only). It solves a problem the click log shows nobody has, and it is the single worst maintenance-per-value item on the list.

**R6 Daily brief: DEFER, out of repo.** If a daily brief system exists, that system pulls from the click log and cswap JSON; switchdeck ships nothing. A one-line note in that repo's backlog, not this one.

**R7 Codex account switching: KEEP THE GATE, which means DEFER indefinitely.** The gate ("if and only if a second Codex account exists") was correctly designed and has not fired. Zero Codex clicks since ship day makes it doubly dead. Correctly gated features that never fire are the roadmap working as intended.

**R8 Packaging: KEEP, promoted.** This is the only old-roadmap item that serves the system-level polish bar. Today the "app" is a Python script in an external venv launched by a hand-edited plist whose repo copy still points at `/Users/YOU/Documents/GitHub/switchdeck` (plist:11), a path convention the repo left on 2026-07-30. A portfolio menu bar app that does not appear in the process list as an app, has no bundle, no icon in the bar (a text glyph "⇄" at switchbar.py:200, while a purpose-built two-card template icon sits unused in design/menubar, BRAND.md:23), and cannot survive a venv deletion is not at any craft bar. Promoted into the candidate set.

## 6. Red team pass 2: candidate set and scoring

Candidates C1-C10: pass-1 survivors plus new proposals. Scored 0-2 per criterion: (a) survives a hostile senior reviewer, (b) reduces resume cost rather than adding configuration, (c) zero paid dependencies and no fragile or elevated permissions, (d) moves the system-level polish bar, (e) ships in one focused build session, (f) maintainable by one person in six months. Max 12.

| # | Candidate | a | b | c | d | e | f | Total | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| C1 | Retire the Codex surface: default CODEX_USAGE_CMD to None, remove the row from the shipped default, fix the 300s refresh defect, make the local-only badge true | 2 | 1 | 2 | 0 | 2 | 2 | 9 | TOP 5 |
| C2 | Engine contract: pin the validated cswap version, check at startup, show an explicit "engine X unvalidated (validated: Y)" row on mismatch; upgrade to and revalidate 0.25.x | 2 | 1 | 2 | 0 | 2 | 2 | 9 | TOP 5 |
| C3 | Pre-lockout notification: when the active account's 5h window crosses a threshold and another slot has headroom, notify once: "slot 1 at 85%, slot 2 at 12%, switch now". Data already polled every 300s | 2 | 2 | 2 | 1 | 2 | 2 | 11 | TOP 5, rank 1 |
| C4 | Global hotkey switch via Carbon RegisterEventHotKey (the no-permission path; the event-tap path needs Accessibility and is disqualified) | 1 | 2 | 1 | 2 | 1 | 1 | 8 | DEFER to C10 |
| C5 | Packaging plus rename completion: .app bundle, LSUIElement, brand template icon in the bar, plist label migration to com.shashank.switchdeck, code identity says SwitchDeck | 2 | 0 | 2 | 2 | 1 | 2 | 9 | TOP 5 |
| C6 | Resume card: post-switch notification carries recovery context read from local Claude state (live session count, active org, last project cwd): "Switched to slot 2. Slot 1's live session finishes its reply and picks up the new credential in ~30s" | 1 | 2 | 2 | 1 | 2 | 1 | 9 | TOP 5 |
| C7 | Auto-switch surfacing (R3 rewritten): enable engine auto mode dry-run, narrate interventions | 1 | 2 | 2 | 1 | 1 | 1 | 8 | NEXT, blocked on C2 |
| C8 | Switch-reason capture: prompt for why after each switch to feed the gate | 0 | 0 | 2 | 0 | 2 | 2 | 6 | KILL, adds interaction cost to the exact moment the tool exists to make cheap |
| C9 | Menu craft pass standalone (usage mini-bars, submenus) | 1 | 0 | 2 | 1 | 2 | 2 | 8 | FOLD into C5 |
| C10 | Swift MenuBarExtra rewrite wrapping cswap: the native portfolio piece, hotkeys via the MIT KeyboardShortcuts package | 2 | 1 | 2 | 2 | 0 | 1 | 8 | HORIZON, fails one-session hard |

Attacks on my own survivors: C1 is subtraction, and subtraction as a headline looks like padding; it stays because the local-only claim is currently false in a public repo, which is a credibility hole, not a nitpick. C3 risks notification spam; acceptance criteria below cap it at one notification per window crossing. C6 risks reading Claude Code internals that shift between versions; it reads only `~/.claude.json` and the sessions dir the app already reads, and degrades to the current notification text on any parse failure. C5's plist label migration breaks the running LaunchAgent if done carelessly; the owner's private consolidation notes already document the bootout-then-bootstrap procedure. C4 dies on honesty: Carbon hotkey registration from Python via ctypes is exactly the hack a hostile reviewer flags, and its natural home is C10 where it costs three lines.

## 7. Native and competitor overlap

| Capability | Native macOS Tahoe 26 | Raycast-class | Shortcuts | Verdict |
|---|---|---|---|---|
| Switch Claude Code accounts | Nothing. macOS has no concept of Claude account identity | A script command can shell out to `cswap switch N`; nobody ships this today, but any user could assemble it in 10 minutes | Same, a Run Shell Script action | Activation alone is NOT a moat |
| Per-account quota at a glance, always visible | No | No persistent glanceable surface; Raycast shows results on invocation | No | Differentiated |
| Verified switch plus live-session awareness (the ~30s Keychain cache warning) | No | No, a script command fires and forgets | No | Differentiated, and it is the single most craft-dense thing in the repo |
| Usage/cost dashboards | No | ccusage, CodexBar, and the sibling claude-burnrate own this space | n/a | NOT differentiated; do not build dashboards here |
| Auto-switch before lockout | No | No | No | Owned by upstream cswap 0.25.x; the app's role is narration only |

What remains genuinely differentiated: the combination of identity-keyed slots, always-visible per-account headroom, verified switching with live-session awareness, and zero elevated permissions, in one surface. No single piece is a moat; the assembled whole is not replicated anywhere, including by the upstream engine, which is a CLI. The differentiation is real but narrow, and it is one upstream menu bar feature away from erosion: if claude-swap ships its own bar app, this repo's remaining value is craft and design, which is another reason C5 and eventually C10 matter.

## 8. Core value proposition check

The proposition: when a quota wall stops work, get onto the account with headroom in one action, with proof it worked, without a browser login dance. After the overlap analysis it survives, because nothing native or Raycast-shaped covers headroom visibility and verified switching together. What would drift from it: dashboards (owned by siblings), Codex anything (dead by click log), cross-machine anything (no user). The top 5 below was checked against this proposition and revised once: an earlier draft ranked packaging first for the polish bar; that inverts the priority, because craft on top of a false local-only claim and an unpinned rotting engine is polish on sand. Trust items precede craft items.

## 9. FINAL TOP 5, ranked

Gate note that governs all five: items 1 and 2 are integrity and maintenance work, legitimate under the failed gate. Items 3 through 5 are features; shipping them requires the owner to ratify the amended gate in open question 1, or they wait.

**1. Pre-lockout switch prompt (C3).**
Rationale: this is the core proposition made proactive; the cheapest resume is the lockout that never happens. The data is already in memory every 300 seconds.
Files: switchbar.py only (threshold check in `refresh`, one state flag per window to fire once per crossing, threshold constant with a local_settings override).
Permissions: none new; uses existing best-effort notifications. Failure mode when notification permission is revoked: silent no-op, menu still shows the numbers.
Acceptance: with active account above 80% on the 5h window and any other slot below 50%, exactly one notification fires per crossing; no repeat until the window resets; click log records `threshold-alert`.
Build size: small, one session with margin. Non-scope: no auto-switching, no configuration UI beyond one optional constant.

**2. Engine contract pin and drift alarm (C2).**
Rationale: the app's entire capture and restore path is delegated to an engine that is six minor versions behind, unpinned, unchecked, and that changed its feature surface (auto mode) since validation. This is the largest silent-failure risk in the repo, and the repo's own STATE.md named it and nothing happened.
Files: switchbar.py (startup `cswap --version` check against a VALIDATED_ENGINE constant, warning row on mismatch), README.md (validated-version line).
Permissions: none.
Acceptance: with a mismatched engine, the menu shows an explicit unvalidated row and everything else still works; with the pinned version, no row. Upgrade to 0.25.x, re-run the CLAUDE.md v0 validation checklist (round-trip switch both directions, same-email slot integrity, MCP survival), record the result in the decision log.
Build size: small. Non-scope: no auto-update, no version manager.

**3. Retire the Codex surface and make local-only true (C1).**
Rationale: zero Codex clicks in 40 days (VERIFIED, click log); the default `npx -y ccusage@latest` pings the npm registry, and the refresh defect makes that every 5 minutes, under a public "local-only" badge. Dead feature, false claim, network chatter: all three end here.
Files: switchbar.py (CODEX_USAGE_CMD defaults to None, fix the `_sender` guard so timer ticks do not trigger Codex refresh), README.md (feature list and badge honesty), local_settings.example.py.
Permissions: none. Failure mode: none; users who want the row set one local_settings line, documented.
Acceptance: default install makes zero network calls; with the row enabled, ccusage runs at CODEX_REFRESH_SECONDS, verified by timestamped log lines.
Build size: small. Non-scope: do not delete the Codex code paths; default them off. The one existing user has a Codex launcher configured in local_settings.py.

**4. Resume card (C6).**
Rationale: the highest resume cost sits in the 30 seconds after a switch: did it work, which account is live, what was I doing. The v1.6 live-session warning is half of this; the resume card completes it with active org, live session count, and the projects those sessions are in, read from files the app already reads.
Files: switchbar.py (extend `live_claude_sessions` to surface cwd or project when the session JSON carries it, richer post-switch notification text).
Permissions: none; reads `~/.claude.json` and `~/.claude/sessions/*.json` only. Failure mode: any parse miss degrades to the current v1.6 text; never blocks a switch.
Acceptance: a switch with one live session in a known project produces a notification naming the target label, the active org, and that project; a switch with zero sessions produces the current org-confirmation text.
Build size: small to medium, one session. Non-scope: no window management, no app restoration, no session content.

**5. Packaging, rename completion, and the bar icon (C5, absorbing C9).**
Rationale: the system-level polish item. One name everywhere (SwitchDeck in class, filename, plist label, notifications), an .app bundle with LSUIElement, and the brand's two-card template icon in the menu bar instead of a text glyph. The design system exists and is unused by the running product, which is the definition of unfinished.
Files: switchbar.py renamed and re-classed, com.shashank.switchbar.plist replaced by com.shashank.switchdeck.plist, design/menubar template wired in via rumps icon support, README install section updated (it still points at ~/Documents/GitHub, README.md:73, stale since the 2026-07-30 move).
Permissions: none. Migration hazard: the label change requires launchctl bootout of the old agent then bootstrap of the new one, procedure documented in the owner's private consolidation notes; done wrong, the app stops launching at login, which is recoverable but embarrassing.
Acceptance: process list shows SwitchDeck, the bar shows the template icon rendering correctly in light and dark menu bars, login relaunch works, old plist gone.
Build size: one full session, the largest of the five. Non-scope: code signing and notarization decisions deferred; the Swift rewrite (C10) explicitly not started.

Explicitly deferred with reasons on record: C4 hotkeys (belongs in C10 where it is trivial and permission-clean), C7 auto-switch narration (blocked on item 2's validation), C10 Swift rewrite (the real portfolio horizon, not a session).

## 10. WHAT IS WORKING (evidence)

- The core loop is alive and used: 21 menu bar switches across 6 weeks, latest this morning 2026-08-17 07:21, including switches with live CLI sessions. VERIFIED, click log.
- The app is running right now under launchctl, exit status 0, PID 1109, from the canonical repo path. VERIFIED.
- Verified switching with live-session awareness (v1.6) shipped and functions as designed. VERIFIED, switchbar.py:217-241, log entries with `live_cli=` counts.
- Security hygiene is genuinely above the bar for a repo this size: gitleaks CI, hardened .gitignore, gitignored identity labels, history rewritten to remove work-email authorship, decision log with logged gate exceptions. VERIFIED.
- Repo is clean, in sync with origin, zero TODO debt, MIT licensed, Claude credited (README.md:134). All fixed product constraints except local-only are currently satisfied. VERIFIED.

## 11. WHAT IS NOT WORKING (evidence, root cause)

- The behavior gate failed and nobody was watching. No two consecutive 3+ weeks in the click log; CLAUDE.md:14 says nothing ships until it passes; six weeks passed with no evaluation. Root cause: the gate had no owner and no evaluation trigger; governance by document, enforcement by nobody.
- The local-only claim is false as shipped. Default Codex command is `npx -y ccusage@latest`, a network call, made every 5 minutes because of the timer-sender defect at switchbar.py:181-183. Root cause: the rumps Timer passes itself as sender and the guard mistakes it for a human click; the badge was written for the switching path and nobody audited the Codex path against it.
- The engine underneath is rotting silently: 0.19.0 installed, 0.25.0 upstream, no pin, no check, while docs/STATE.md:38 names exactly this risk. Root cause: risk documented, remediation never scheduled; dormancy did the rest.
- The Codex feature is dead weight: 4 clicks, all on ship day. Root cause: feature shipped inside the v1.5 gate exception without its own behavior gate; the roadmap's own philosophy applied to it retroactively kills it.
- The rename is incomplete: SwitchBar in every user-visible and system-visible identity of a product branded switchdeck. Root cause: the brand sprint (2026-07-28) shipped assets and README and stopped at the code boundary because the plist migration is operationally annoying (hazards.md:16).
- The tracked plist and README install path reference `~/Documents/GitHub/switchdeck`, a location this repo left on 2026-07-30. Root cause: consolidation remapped the installed plist, not the tracked template. VERIFIED, plist:11, README.md:73.

## 12. Blocking open questions (max 3)

1. **Gate ratification.** The v1.5 gate failed as written but usage is real and bursty. Proposed amendment: "switch action used in 4 of any 6 consecutive weeks", which the current log already satisfies (weeks of Jul 6, Jul 27, Aug 3, Aug 10, Aug 17 all have use). Ratify, replace, or hold the line; top 5 items 3 through 5 wait on this.
2. **Codex row retirement.** local_settings.py configures a Codex launcher, but the log shows zero Codex use since ship day. Confirm default-off is acceptable for your own machine, not only for the shipped default.
3. **Is switchdeck the flagship polish piece, or one of several?** If it is the piece, item 5 should be skipped in Python and the effort should go straight to the Swift MenuBarExtra rewrite (C10) next quarter. If it is one of several, item 5 as scoped is the right ceiling. This decision changes where the packaging session is spent.

---

Audit complete, phase gate honored: no implementation, no repo mutation. Deliverable 2, the project's first continuity handoff, was written to the owner's private handoff system.

---

# Addendum, 2026-08-17 (same day): owner decisions and a correction that revises the top 5

## The correction, verified

claude-swap 0.25.0 ships its own macOS menu bar app. VERIFIED against PyPI: install via `uv tool install 'claude-swap[menubar]'`, launch via `cswap menubar`; it shows "every account's 5h / 7d / spend usage and switches with a click (specific / rotate / best / next-available)", includes the TUI's account management actions, and offers background auto-switching sharing the `cswap auto` configuration. Additionally, every JSON payload carries a `schemaVersion` field, currently "1". VERIFIED.

Consequences, stated plainly:

- **Section 7 was stale the day it was written.** The claimed differentiation (always-visible per-account headroom plus click-to-switch in one surface) has been upstream functionality since 2026-08-11. The erosion risk Section 7 called "one upstream menu bar feature away" had already happened.
- **Original top 5 item 1 (pre-lockout prompt) is KILLED by this audit's own R3 logic.** The engine owns thresholds and auto-switching; an app-side threshold notification duplicates upstream. Replaced by C7: upgrade to 0.25.x, run `cswap auto` in dry-run, narrate interventions in notifications and the click log. The app narrates; the engine acts.
- **The engine contract item gains a second pin:** pin `schemaVersion` alongside the version string. A schemaVersion mismatch is the precise, machine-checkable form of the drift the original item guarded against.
- **Reclassification:** Codex retirement plus the timer defect fix plus badge honesty is integrity work and gate-exempt. The killed pre-lockout prompt was a feature and never was.
- **What differentiation remains:** craft and context. Upstream now owns the utility; what upstream does not do is the resume card (context recovery at the switch moment), the behavior-gate discipline, the design system, and a native Swift surface. switchdeck's case is now craft, and its Python incarnation is interim by declaration.

## Owner decisions, on record

- **Q1 RATIFIED.** Gate amended to: switch action used in 4 of any 6 consecutive weeks. Noted on record as a retrofit to observed usage, not a fresh hypothesis.
- **Q2 CONFIRMED.** Codex row default-off, including on this machine (local_settings.py loses its Codex launcher line when the change ships).
- **Q3 DECIDED by the correction.** Upstream owns the utility; switchdeck's case is craft. Python packaging polish is skipped beyond the rename and plist fix; the Swift MenuBarExtra rewrite (C10) is planned as the flagship polish piece.

## REVISED FINAL TOP 5, ranked (supersedes Section 9)

1. **Engine contract: pin plus upgrade plus revalidation.** Pin the validated cswap version AND the JSON `schemaVersion` in switchbar.py; startup check; explicit unvalidated row on mismatch. Upgrade to 0.25.x and re-run the CLAUDE.md v0 validation checklist. Integrity work, gate-exempt. Everything downstream depends on it.
2. **Codex retirement, timer defect fix, local-only truth.** As scoped in the original item 3, unchanged. Integrity work, gate-exempt.
3. **Auto-switch narration (C7).** Enable `cswap auto` dry-run, surface every intervention as a notification and a click-log entry. Feature, legitimate under the ratified gate. Blocked on item 1.
4. **Resume card.** As originally scoped, with one added prerequisite: verify a rumps notification actually renders on macOS Tahoe 26 from the unbundled Python app before building. If it does not render, the rename/plist work in item 5 (or bundling) becomes this item's prerequisite and the order flips. UNVERIFIED until tested; the audit found notifications are fired best-effort with failures swallowed (switchbar.py:65-69), so silent failure is exactly what the current code would hide.
5. **Rename completion and plist migration only.** SwitchDeck in filename, class, notifications; com.shashank.switchdeck plist label with the documented bootout/bootstrap procedure; stale ~/Documents/GitHub paths fixed in plist and README. No .app bundle, no icon wiring, no signing: the full packaging effort moves to the Swift rewrite, where it is the point rather than polish on an interim surface.

Original items superseded: pre-lockout prompt (killed, upstream), packaging beyond rename (moved to C10). The Swift MenuBarExtra rewrite is the named horizon and the flagship polish piece; it starts as its own scoped effort, not as a tail on item 5.
