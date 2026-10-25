# Debate and adversarial extension design

## Intent and scope

Implement the two distinct workflows in `docs/REQUEST.md`, without UI or a
Thurbox fork. The user's “let's go” follows the external-extension recommendation;
the executable is `thurbox-loop`, not a modification of the core TUI executable.

## Approaches

1. External extension (selected): install Python files through `extension.toml`
   and orchestrate the public `thurbox-cli` API. No upstream maintenance burden.
2. Fork: add core subcommands. This achieves the original command spelling but
   creates an unnecessary dependency on core releases.

## Verified integration

Inspected `Thurbeen/thurbox` at
`12690e3bc5e5c2162c000b073720768a170c289c`:

- `src/session/extension_def.rs`: `[[files]]`, executable payloads, `{home}`.
- `src/cli/sessions.rs`: `session create --agent --repo-path`, returned `id`,
  `cwd`, `worktrees`; `--worktree-branch`, `--base-branch`,
  `--existing-worktree`; `session send`, `get`, and `stop`.
- `src/cli/agents.rs`: registry-resolved `agent launch-args`; no provider SDK
  abstraction or generic structured-output protocol is exposed.
- `docs/ORCHESTRATION.md`: latched hook status does not prove completion;
  workers must write a result artifact. Lifecycle hooks are user-owned and
  must not be installed by extensions.

The adapter creates a fresh registered-agent session for each turn, sends a
prompt referencing an atomic JSON result file with a per-turn nonce, and waits
with a deadline. It stops that session before permitting the next turn. Fresh
sessions prevent hidden conversation history from influencing the first attack.
No model or permission flags are overridden. Hooks provide supervision only.

## Architecture

Python 3.11+, standard library only. `core` owns bounded subprocess execution,
agent protocol, schema validation, atomic persistence and checks. `debate` and
`adversarial` own explicit transition graphs, prompts and reports. CLI and
Thurbox adapter are outside workflow code. Tests inject fake agents and a fake
Thurbox executable; no credentials required.

Debate passes no opposing output to either initial turn. Initial results are
published only after both have finished. Subsequent prompts carry the relevant
structured records. Challenge IDs and rebuttal coverage are validated. Consensus
requires equal explicit decision keys; differing final recommendations remain
UNRESOLVED. Both final recommendations are always preserved in the report.

Adversarial creates a Thurbox-owned isolated worktree before building and retains
it. The reviewer receives task, diff (including untracked files), and objective
checks on its first attack, with no builder narrative. Later attacks receive the
engineering log and all previous findings. Each repair must address every open
finding. Failed checks override SATISFIED. Repeated identical failed evidence
stops as BLOCKED. Max attacks defaults to five. No auto-commit, merge, push,
session deletion or worktree deletion.

## Persistence and safety

Each run has an exclusive directory and atomically replaced `state.json`, full
validated turn artifacts, report, and engineering log. Failures persist terminal
FAILED state and reports. No resume in v0.1: interrupted runs are inspectable.
Configuration and explicit CLI checks are trusted executable configuration;
model output never supplies command arguments. Checks are argv arrays or shell-
split strings, executed without a shell, with bounded time and captured output.
Run files use private permissions and redact common credentials and secret env
values. Prompts request evidence/decisions, never private chain-of-thought.

## Limits and builder decisions

Local repositories and POSIX process groups only in v0.1. Live agents require
their existing permissions to write result files. Prompts enforce reviewer and
debate read-only behavior; this is not an OS security sandbox. The user must use
appropriately restricted registered agents for untrusted repositories. No live
CLI is available in the implementation environment; fake CLI contract tests do
not replace a live integration test. Python is the implementer's choice.
