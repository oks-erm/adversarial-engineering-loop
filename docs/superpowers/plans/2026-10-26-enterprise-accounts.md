# Enterprise Accounts Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans in this session.

**Goal:** Native Accounts panel and CLI for Enterprise profiles and confirmed handoff.
**Architecture:** Private profile store, native Claude auth adapter, account service
over public Thurbox CLI, and a thin Lua pane. No credential export or core fork.
**Tech Stack:** Python 3.11 standard library; Thurbox Lua API.
**Spec:** `docs/superpowers/specs/2026-10-26-enterprise-accounts-design.md`.

## Global Constraints

- Separate CLAUDE_CONFIG_DIR for each Enterprise login; preserve managed policies.
- Five-minute, single-use handoff confirmation; explicit source/target preview.
- No actual Enterprise context transfer without a specific confirmation.
- Do not grant UI capabilities, trust hooks or log credentials.
- User authorized implementation and push; execute natively without another gate.

## Review Focus

- Credential env/routing overrides must fail closed without exposing values.
- Profile symlinks, arbitrary transcript paths and stale plans must be refused.
- Busy or unproven sessions must not be killed during automatic handoff.
- Resume/fork UUID and destination transcript behavior must pass a compatibility
  gate; unsupported real behavior disables handoff honestly.
- UI command arguments must remain literal and require native capability trust.

## Tasks

### 1. Profiles and Claude adapter
Files: `thurbox_loop/accounts.py`, `tests/test_accounts.py`.
Interfaces: `Profiles.add/get/list`; `Claude.status/login/compatible`.
- [x] Write failure tests for private dirs, slug/path safety, unique profiles,
  env conflicts, status schema/identity mismatch and whitelisted output.
- [x] Observe RED; implement profiles and bounded native auth status.
- [x] Run targeted tests and full suite; include in the focused feature commit.

### 2. Sessions and confirmed handoff
Files: `thurbox_loop/accounts.py`, `tests/test_accounts.py`.
Interfaces: `Accounts.start/preview/confirm` with injected Claude/Thurbox adapters.
- [x] Test persisted env, profile metadata, stop refusal, stale/expired/reused
  plans, locking, immutable snapshot, fork args, failures and recovery evidence.
- [x] Observe RED; implement conservative handoff gate and audit records.
- [x] Verify native signed-out CLI status and fail-closed compatibility gating.
  Real native fork/restart proof runs only after user Enterprise login.
- [x] Run targeted/full tests; include in the focused feature commit.

### 3. CLI and Accounts pane
Files: `thurbox_loop/{accounts,accounts_ui}.py`, `ui/accounts.lua`, account CLI tests.
- [x] Test argument handling, safe UI command generation, non-destructive install,
  layout backup and idempotence before implementing.
- [x] Add accounts subcommands, interactive SSO login and pane worker actions.
- [x] Read installed UI docs; run real `plugin check` and inspect terminal render.
- [x] Do not grant capabilities; clearly show native trust instruction.

### 4. Distribution and documentation
Files: manifest, versions, AGENTS.md, brief `docs/ACCOUNTS.md`, README link.
- [x] Include all new runtime/UI payloads; verify copied installation.
- [x] Run full tests, compileall, installed CLI help and applicable live tests.
- [ ] Independent review and regression fixes complete; commit, push, inspect remote CI.

## Ledger

- Ruling: reuse the clean feature checkout, not another worktree.
- Ruling: do not claim two-account authentication/handoff is verified without
  real authenticated profiles. Capability probing alone is not sufficient.

- Implementation ruling: keep the small feature in one service module and one
  UI delivery module rather than splitting into speculative subpackages.
- Native bootstrap ruling: persistent agent-arg resume/fork flags would replay
  the snapshot on restart. Fork once through native Claude, verify the target
  UUID transcript, then create Thurbox with --resume UUID. No core fork needed.
- Real login is unavailable in this session. Native Claude 2.1.308 signed-out
  status/config-directory was verified; real Enterprise fork gate remains closed.
- Independent review findings fixed: unique UI request results; effective tmux
  session environment; destination UUID recovery; registry lock before spawn;
  Unicode-safe Lua generation. Source remains stopped throughout handoff.
