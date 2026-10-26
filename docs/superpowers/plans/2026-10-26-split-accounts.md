# Split Accounts Implementation Plan

> Use superpowers:executing-plans inline; independent review before push.

**Goal:** The user's requested independent account-only repository and extension.
**Architecture:** `thurbox_accounts` owns profiles, native auth/handoff and the Lua
pane. Minimal private persistence, command runner and public Thurbox transport
helpers are local to the new package. No workflow modules or shared dependency.
**Constraints:** Preserve existing account data and UI ownership; do not copy or
inspect credentials or grant capabilities. Retain the five-minute handoff gate.

- [x] Test standalone CLI, isolated payload and no workflow imports (RED observed).
- [x] Extract account-only package, launcher, tests and real tmux smoke.
- [x] Remove account runtime/payload/tests/docs from this workflow extension.
- [x] Run both suites, compile checks and real account/workflow smoke.
- [x] Install separate extension, rebind owned pane, check live UI, review.
- [ ] Commit/push both repositories and inspect remote CI status.

Decisions: new repo/CLI name thurbox-accounts; new repository private by default;
legacy private data path retained to avoid credential or transcript migration.

Verification: standalone suite22, workflow suite51, compile checks, wheel resource
inspection and real tmux smoke passed. Independent review found no split regressions.
Live pane rebinding passed without trust grants or account state migration.
