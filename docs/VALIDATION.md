# Installation and integration validation

Verified on macOS ARM64, 26 October 2026.

## Installed components

- Official Thurbox/thurbox-cli v2.75.2 release binaries in `~/.local/bin`.
- Release archive SHA-256 matched the GitHub release digest:
  `9dac69e95daf28a80ddb43d5f8e714870b56b2de6e7e1fdc460802d72b2b84df`.
- tmux 3.8 installed through Homebrew.
- Extension installed through the actual `thurbox-cli extension install` command
  at `~/.config/thurbox/extensions/adversarial-engineering-loop`.
- `~/.local/bin/thurbox-loop` points at the installed launcher.
- Real `extension status` reported active, healthy and not stale.

Homebrew performed its automatic update/cleanup while installing tmux. Its
dependency changes included ca-certificates, OpenSSL 4, libevent, ncurses,
utf8proc and jemalloc; it also migrated the existing whisper-cpp formula name
to whisper.cpp. No existing agent sandbox or approval policy was changed.

## Real Thurbox integration

The installed runtime was exercised with real Thurbox/tmux, an isolated registry
and SQLite database, and controlled stdin agents. No Claude/Codex credentials
were needed for these two end-to-end tests:

- Debate: eight fresh participant sessions, four rounds, CONSENSUS report.
- Adversarial: Thurbox-created isolated worktree, builder introduces a real
  `normalize(None)` failure, objective checks fail, reviewer finds C-001,
  builder repairs C-001 and CHECK-001, second attack SATISFIED, outcome PASS.
- All 13 created sessions stopped; the real session database confirmed their
  stopped status. Retained branch/worktree verified.
- Fixture tests were independently executed by the controlled adversary.

Reproduce with `python3.11 examples/live_smoke.py`. Pass `--extension-root` to
test the installed runtime rather than source. This test intentionally uses
its own configuration and disables builtin hook delivery in that configuration
on older releases. Thurbox 2.75.2 has no preinstalled hook extension manifests.

## Real Codex turn

Codex v0.162.0-alpha.17.2 was already authenticated through ChatGPT. Its initial
turn could not submit because startup required folder trust. After the user
explicitly approved trusting only the generated test folder, the next startup
screen requested review of six new/changed hooks. The test selected **Continue
without trusting**; no hook trust was granted.

The ready, fresh session then received the installed adapter's schema/nonce
contract. Codex returned `{"answer": "transport-ok"}` in the required artifact,
the nonce/schema validation passed, and the adapter stopped that session.
The test harness reused the manually prepared session for this single turn;
normal workflow behavior still creates a fresh session on each turn.

This proves the result protocol with an authenticated provider after startup.
It does not prove unattended first-run startup, the full default provider pair,
or real model performance across either complete workflow. Claude was absent
during that earlier test; its later installation is recorded below.

## Automated checks

The unit/CLI/fixture suite, compileall, launcher help, copied manifest payload,
and credential-free smoke are required before pushing. Tests that kill timed-out
process groups require an environment permitting that operation: a sandboxed
run was denied `killpg`; the unsandboxed run passed.

Final automated suite: **49 tests passed**. The installed-runtime live smoke
completed CONSENSUS / PASS in two adversarial attacks and stopped its test-only
heartbeat keeper after checking all session states.

Real integration exposed a diagnostic defect: Thurbox can return its error as
JSON on stdout with empty stderr. Version 0.1.1 extracts that error instead of
reporting an empty failure message; a regression test reproduces that contract.

No deployment or production data was involved. CI status is checked after push;
this repository initially has no configured workflow.

## Extension split — 2026-10-26

Account switching was extracted to the independent thurbox-accounts repository.
Workflow extension 0.2.1 no longer ships or exposes the Accounts CLI or pane.
The workflow suite passes 51 tests, compileall passes, and the fixture smoke
returns debate CONSENSUS / adversarial PASS in two attacks. Existing private
account data remains owned by the standalone extension, without migration.
