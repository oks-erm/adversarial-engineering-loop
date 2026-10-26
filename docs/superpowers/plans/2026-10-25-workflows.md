# Debate and Adversarial Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan
> in this session. Steps use checkbox syntax for tracking.

**Goal:** Deliver both bounded workflows with installable CLI, reports and tests.

**Architecture:** Separate state machines over a small injected Agent protocol.
Thurbox session adapter owns lifecycle and worktree integration; core owns atomic
state, strict validation, checks and safe subprocess execution.

**Tech Stack:** Python 3.11 standard library, unittest, TOML configuration.

**Spec:** `docs/superpowers/specs/2026-10-25-workflows-design.md`, `docs/REQUEST.md`.

## Global Constraints

- Exactly four debate phases; no third judge.
- Adversarial default MAX_ROUNDS = 5; SATISFIED plus passing checks is success.
- No model-generated shell commands; no merge/push/deletion of user work.
- No real credentials in automated tests. Preserve evidence on failures.

## Review Focus

- Partially written/malformed output must fail, never imply approval.
- Worktree setup must not run a builder in the caller's checkout on failure.
- New findings and rejected findings must survive subsequent review rounds.
- A stale status or result from another turn must not finish a turn.
- Failing checks and dirty/untracked code must be visible to the adversary.

### Task 1: Core and debate

Files: `thurbox_loop/core.py`, `thurbox_loop/debate.py`, `tests/test_debate.py`.
Interfaces: `Agent.run(prompt, cwd, mode, schema) -> dict`,
`Debate.run(question, context, criteria, constraints) -> dict`.

- [x] Write tests for independent positions, persisted artifacts, challenges,
  rebuttal coverage, final decisions, consensus/unresolved, failure transitions.
- [x] Run `python3.11 -m unittest discover -s tests -v`; confirm missing behavior.
- [x] Implement atomic Store, strict schemas and Debate with deterministic report.
- [x] Run targeted tests and full suite.

### Task 2: Adversarial

Files: `thurbox_loop/adversarial.py`, `tests/test_adversarial.py`.
Interfaces: `Adversarial.run(task) -> dict`; injected `checks(cwd) -> list[dict]`.

- [x] Test satisfied, repair, multiple/new/rejected findings, blocked, max rounds,
  failed checks, malformed verdict, crashes and report persistence.
- [x] Observe failure; implement finding ledger, first-attack independence,
  evidence capture including untracked files and bounded termination.
- [x] Run targeted tests and full suite.

### Task 3: Runtime and Thurbox integration

Files: `thurbox_loop/runtime.py`, `thurbox_loop/thurbox.py`,
`tests/test_runtime.py`, `tests/test_thurbox.py`.
Interfaces: `ThurboxAgent.run`, `Thurbox.create_worktree`, `run_checks`.

- [x] Test literal argv, exit failure, timeout cleanup, secret redaction,
  worktree validation, result nonce, malformed output and session cleanup.
- [x] Observe failure; implement bounded subprocess and public CLI adapter.
- [x] Run targeted tests and full suite.

### Task 4: Distribution, CLI and smoke artifacts

Files: `thurbox_loop/cli.py`, `bin/thurbox-loop`, `pyproject.toml`,
`extension.toml`, `README.md`, `AGENTS.md`, `examples/`, `tests/test_cli.py`.

- [x] Test argument/config validation, CLI exits, install payload coverage and
  fake-agent end-to-end smoke runs; observe failure before implementation.
- [x] Implement CLI, complete documentation and reproducible smoke script.
- [x] Generate example reports from actual fake-agent runs.
- [x] Run full unittest suite, compileall, CLI help and smoke script.
- [x] Review all changes; record final evidence and live-integration limitation.

## Execution ledger

- Ruling: reuse the clean dedicated clone on a feature branch; no additional
  worktree is necessary for implementing the extension itself.
- Ruling: the user approved proceeding with the recommended external extension;
  use native execution here, with no pushes or publication.
- Task 1: seven debate tests passed after missing implementation was observed.
- Task 2: thirteen initial adversarial tests passed, including real Git evidence.
- Task 3: fourteen runtime/adapter tests passed against a subprocess CLI double.
- Task 4: source launcher, copied installation payload and both full CLI flows
  passed. Fake-agent smoke uses real regression tests and a retained worktree.
- Final review: independent reviewer found an untracked binary/mode mutation
  bypass. Both reproductions failed before the fix and passed after adding raw
  SHA-256 and file mode fingerprints. Reviewer found no additional material issue.
- Additional regression fixes: poll deadlines preserve TimeoutError; report
  check rows stay on one Markdown line; timing jitter does not hide no-progress.
- Live Thurbox and real authenticated agents remain unverified: the executable
  is absent here. No CI/deployment or publishing was attempted.
- Final verification: 47 unittest tests passed; compileall and both CLI help
  commands passed. Copied manifest payload runs outside the source checkout.
- Builder-crash regression: partial changes are captured in failure evidence.
  Independent review findings were fixed; no deferred minor findings.
