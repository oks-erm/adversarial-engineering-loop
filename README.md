# Thurbox Debate + Adversarial Loop

Two separate workflows, installed as an external Thurbox extension:

- **debate**: independent positions → cross-examination → rebuttals → final
  positions → deterministic consensus or unresolved decision report.
- **adversarial**: builder changes code → adversary attacks → builder repairs →
  fresh attack, until SATISFIED and configured checks pass. Default: five attacks.

No UI or Thurbox fork is required. Command names are `thurbox-loop debate` and
`thurbox-loop adversarial`; extensions cannot add core `thurbox` subcommands.

## Requirements and installation

Python **3.11+**, Git, a local working Thurbox CLI and its supported multiplexer,
and registered authenticated coding agents (defaults: `claude` and `codex`).
No Python runtime dependencies or model SDKs are needed.

From a clone:

```sh
./bin/thurbox-loop --help
export PATH="$PWD/bin:$PATH"
```

Or install the extension into Thurbox's extension home:

```sh
thurbox-cli extension install ./
# After this source is merged into the default branch, remote installation is:
# thurbox-cli extension install git+https://github.com/oks-erm/adversarial-engineering-loop.git
```

Use the `home` path printed by installation and add its `bin` directory to PATH.
The manifest copies the launcher and every runtime module; it does not change
your agents, permissions, lifecycle hooks, automations or shell configuration.
Alternatively, `python3.11 -m pip install .` installs a console command (build
requires setuptools). Running from source needs no package installation.

## Debate

```sh
thurbox-loop debate \
  --repo /path/to/project \
  --agent-a claude --agent-b codex \
  --context 'A small service with a fixed lifecycle' \
  --criterion 'Operational simplicity' \
  --constraint 'No third LLM judge' \
  'Should this service use LangGraph or a deterministic state machine?'
```

Each participant starts with the same question, context, criteria and constraints.
Neither receives the other's initial answer. Both initial answers are persisted
only after both independent turns finish. Every turn uses a fresh agent session,
so prior conversational history cannot leak into the next initial position.
The initial positions, critiques and rebuttals are supplied explicitly to later
turns. Every rebuttal must map to an actual opposing challenge.

There is exactly one round of each kind. Consensus is conservative: the final
`decision_key` **and exact recommendation text** must match. Equivalent wording
may therefore yield UNRESOLVED; disagreement is never erased by a third judge.
Both full final recommendations, confidence, supporting evidence, remaining
risks and proposed resolving experiments are preserved in `DEBATE_REPORT.md`.

Artifacts default to `.thurbox/debate/<id>/`: `state.json`, `request.json`,
`question.md`, participant/phase JSON and Markdown, `sessions.json`, report.
Use `--output /new/path` to choose a new exclusive run directory.

## Adversarial

```sh
thurbox-loop adversarial \
  --repo /path/to/project \
  --builder claude --adversary codex --max-rounds 5 \
  --check 'npm test' \
  'Implement idempotent request processing'
```

Thurbox creates `adversarial/<run-id>` in an isolated worktree from committed
`HEAD` (or `--base-ref <ref>`). Uncommitted caller changes are preserved and are
**not copied** into the worktree. Use a committed base containing the context
you want the builder to use. The worktree and session records are retained;
only this run's active agent processes are stopped. No code commits, merge,
push or deployment is performed automatically.

The first attack receives task, repository, diff (including untracked files),
and actual objective-check results. Builder commentary is excluded. Subsequent
attacks receive the engineering evidence log and all previous findings, and
must reassess rejected/resolved findings as well as look for additional defects.
A reviewer that changes tracked or nonignored files during its turn cannot
approve the altered implementation: that turn fails. This detects changes;
it does not roll them back.

Every open finding requires an ACCEPTED, REJECTED or PARTIALLY_ACCEPTED builder
response. Rejections require evidence. The reviewer independently determines
resolution. Check failures become reserved `CHECK-###` findings and override
SATISFIED. Three unchanged attacks stop as BLOCKED. `--max-rounds` bounds attacks,
not builds; the initial build plus at most `max-rounds - 1` repairs run.

Outcomes: PASS, PASS_WITH_WARNINGS (no objective checks configured), BLOCKED,
MAX_ROUNDS_REACHED, FAILED. A valid unresolved debate is a completed workflow.
CLI exit codes: **0** complete; **1** execution/protocol failure; **2** invalid
configuration/arguments; **3** blocked or round limit; **130** interrupted.

Artifacts default to `.thurbox/adversarial/<id>/`: `state.json`, task,
validated build/attack JSON, per-attack repository/check evidence,
`ADVERSARIAL_LOG.md`, `ADVERSARIAL_REPORT.md`, `sessions.json`. Final stdout
contains JSON with outcome, report path, worktree, branch and commit. The final
commit can still be the baseline while the reviewed changes are uncommitted.

### Objective checks

Add trusted `.thurbox/loop.toml` in the caller repository, or pass `--config`:

```toml
[adversarial.checks]
commands = [
  "uv run pytest",
  "uv run ruff check .",
  ["uv", "run", "mypy", "src"]
]
```

`--check` appends to configured checks. Checks execute in the isolated worktree.
Strings use POSIX argv splitting; arrays avoid quoting ambiguity. No shell is
used: pipes, redirection, `&&`, command substitution and environment expansion
are not supported. Put complex trusted checks in a repository script.
There is no language-specific auto-detection. Model-generated strings never
become check commands. Treat the configuration like a build script: it executes
code with your permissions.

`--check-timeout` bounds each check (default 600 seconds); `--agent-timeout`
bounds waiting for each agent result (default 600 seconds), with an additional
bounded session-creation/stop interval. Check output keeps a bounded tail and
marks truncation; Git evidence over 2 MB fails rather than silently omitting it.

## Actual Thurbox integration

Inspected upstream commit
[`12690e3`](https://github.com/Thurbeen/thurbox/tree/12690e3bc5e5c2162c000b073720768a170c289c).
Compatibility is tied to these public contracts, not an invented version floor:

| Upstream location | Contract used |
|---|---|
| `src/session/extension_def.rs` | `extension.toml`, `[[files]]`, executable payloads |
| `src/cli/sessions.rs` | `session create --agent --repo-path`, JSON `id`, `cwd`, `worktrees` |
| `src/cli/sessions.rs` | `--worktree-branch`, `--base-branch`, raw `--command` / `--arg` holder |
| `src/cli/sessions.rs` | `session send`, `session get`, `session stop` |
| `docs/ORCHESTRATION.md` | Worker result artifacts; latched hook state is supervision only |

Registered agent sessions let Thurbox own agent arguments and lifecycle hooks.
The adapter never hardcodes provider SDKs, models or permission flags. A private
temporary prompt file supplies a strict JSON schema and nonce. The agent must
atomically write `{ "nonce": "...", "result": { ... } }` at the supplied path.
Malformed output, wrong nonce, agent loss and deadlines fail visibly. Each agent
session is stopped before the next turn. Failed stops block further execution
and leave session identifiers in the journal for manual inspection.

The worktree helper launches a harmless Python sleeper as a Thurbox session,
validates the returned branch, path and Git common directory, then stops the
holder. Stopping retains its worktree. No extension lifecycle hooks are installed.

## Architecture

```text
thurbox_loop/
  core.py          Agent protocol, strict schemas, redaction, atomic state
  runtime.py       bounded argv execution, checks, process-group cleanup
  thurbox.py       public CLI/session adapter and isolated worktree helper
  debate.py        four debate rounds and deterministic report
  adversarial.py   build/attack/repair state machine, Git evidence and reports
  cli.py           trusted configuration, arguments and exit status
tests/             fake agents, fake Thurbox subprocess and real Git/check tests
examples/smoke.py   runnable demonstration with a real defect and repair
```

## Validation and examples

```sh
python3.11 -m unittest discover -s tests -v
python3.11 -m compileall -q thurbox_loop examples tests
python3.11 examples/smoke.py
```

Smoke runs need only Python and Git. They create and retain a temporary sample
repository/worktree; supply `--output /new/path` to select the artifact directory.
The fake reviewer actually reruns regression tests. Demonstrated flows:

```text
DEBATE: question → independent positions → challenges → rebuttals
        → final positions → CONSENSUS report
ADVERSARIAL: build → failing regression test → finding → repair
             → new attack → passing regression tests → SATISFIED → PASS report
```

Generated examples: [Debate report](examples/reports/DEBATE_REPORT.md),
[Adversarial report](examples/reports/ADVERSARIAL_REPORT.md),
[Engineering log](examples/reports/ADVERSARIAL_LOG.md).

With Thurbox and its multiplexer installed, run the opt-in integration check:

```sh
python3.11 examples/live_smoke.py --thurbox-cli /path/to/thurbox-cli
# Validate an installed extension's runtime instead of the source checkout:
python3.11 examples/live_smoke.py --thurbox-cli /path/to/thurbox-cli \
  --extension-root /path/to/extension/home
```

This uses a separate temporary Thurbox registry/database and controlled test
agents through **real Thurbox sessions**, without LLM calls. It verifies all
13 sessions stop and the worktree is retained. Existing personal agents and
hooks are not changed. Results from the actual installation are recorded in
[validation evidence](docs/VALIDATION.md).

## Limits and assumptions

- v0.1 supports local POSIX hosts only; no Windows process-tree or remote-host
  orchestration. No resume/retry after interruption; retained state is inspectable.
- Real Thurbox **2.75.2** and tmux **3.8** have been tested with both full
  workflows using controlled agents. One authenticated Codex JSON turn also
  passed after its interactive startup was handled. The complete default
  Claude/Codex pairing remains unverified: Claude is not installed here.
- Agent read-only rules are prompts plus mutation detection in adversarial mode,
  **not an OS sandbox**. Use suitably restricted registered agents for untrusted
  code. Debate independence concerns supplied context; this is not a security
  boundary against a malicious agent searching the filesystem.
- Agents must have permission to read the private temporary prompt and write its
  result path. Folder trust, hook review and other startup dialogs may prevent
  prompt submission or cause a timeout. Review those dialogs through the agent's
  own interface before unattended use. This extension does not accept them or
  change sandbox/approval policy. The real Codex test reused a fresh session
  after folder approval and skipping untrusted hooks; it did not establish
  unattended first-run readiness.
- Results and evidence are private files with redaction of known secret env
  values and common token patterns. Redaction is best effort; do not configure
  checks or tasks that print sensitive customer data or unknown credentials.
  Agent CLIs and Thurbox manage their own transcripts outside this extension.
- No third judge, UI pane, auto-detection, auto-commit, auto-merge or deployment.
  No runtime third-party Python dependencies. Package installation optionally
  needs setuptools; source/extension execution does not.
