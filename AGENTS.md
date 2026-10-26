# Working on Thurbox Loop

## Purpose and architecture

Two distinct external Thurbox workflows: debate makes decisions without required
code edits; adversarial builds/reviews/repairs code in an isolated worktree.
Read `docs/REQUEST.md` and the design under `docs/superpowers/specs/`.

Python 3.11+, standard library only. `core.py` owns schemas, Agent protocol,
atomic persistence and redaction; `runtime.py` owns bounded command execution;
`thurbox.py` adapts public Thurbox CLI; `debate.py` and `adversarial.py` own
separate state machines/reports; `cli.py` parses trusted TOML and arguments.
No database, migrations, network SDK or provider SDK. Store state as JSON and
human-readable Markdown, with exclusive run directories and atomic writes.

## Commands

```sh
./bin/thurbox-loop --help
python3.11 -m unittest discover -s tests -v
python3.11 -m compileall -q thurbox_loop examples tests
python3.11 examples/smoke.py
# Opt-in: real Thurbox/tmux sessions, controlled agents, no LLM calls:
python3.11 examples/live_smoke.py --thurbox-cli /path/to/thurbox-cli
```

No dependency installation is needed for development. There is no configured
third-party lint/type checker. `python3.11 -m pip install .` optionally builds
with setuptools and installs a console entrypoint. `extension.toml` must list
every runtime module and executable launcher; a test enforces payload coverage.

## Contracts and safety

- Defaults are registry names claude/codex, never model-specific orchestration.
- Initial debate positions must remain independent; do not persist either
  until both finish. Exactly four rounds; preserve unresolved disagreement.
- First attack sees no builder narrative. Every later attack reassesses all
  findings. Failing checks outrank SATISFIED. Default max attacks = 5.
- Commands come only from trusted config/explicit CLI values. Never execute
  arbitrary model output. Use argv, deadlines and process-group cleanup.
- Never overwrite a run directory. Never delete worktrees/session records or
  user changes, auto-merge, force-push, deploy, or change auth/billing/security
  policies without explicit authorization. Stop only sessions this run owns.
- Read-only agent behavior is not a security sandbox. Do not weaken agent
  permissions to make tests/live runs work. Do not commit `.env` or credentials.
- Redact evidence, keep files private, and do not log full environments.
- `THURBOX_*` paths/socket/environment are inherited; do not repurpose HOME or
  CODEX_HOME. No new environment variables or secret settings are required.

## Integration pitfalls

Upstream inspected at `12690e3bc5e5c2162c000b073720768a170c289c`.
`session create` returns `id/cwd/worktrees`. `session stop` preserves worktrees.
`session send/get` supervises agents but latched hook state never proves completion.
Use per-turn nonce-bound atomic result artifacts, strict schemas and fresh
sessions. Installation is manifest file delivery, not core subcommand registration.
See README for exact source paths and live-integration limitations.

Git evidence includes untracked code and changes since the original committed
baseline, even if the builder commits. Oversized evidence fails. Worktree creation
starts from committed HEAD, preserving but not copying uncommitted caller changes.
Objective checks may create files: repository ignore rules should exclude normal
test caches. Reviewer changes to nonignored files invalidate its verdict.

## Validation checklist

Write regression tests before behavioral changes. Run targeted tests then full
unittest suite, compileall, and smoke. Inspect generated reports and final diff,
including untracked files. Test failures, timeouts, malformed results, isolated
worktree refusal, first-turn independence and objective-check precedence.
Live integration requires installed Thurbox plus authenticated agents; do not
claim it passed based on the fake CLI. The opt-in live smoke uses real sessions
with controlled agents and isolated THURBOX_CONFIG_DIR/THURBOX_DATA_DIR. See
docs/VALIDATION.md for verified versions and the limited real Codex test. Startup
dialogs require human review: never automatically trust folders or hooks.
Thurbox errors may be JSON on stdout with empty stderr; preserve their error
field in diagnostics. No CI/CD or deployment is configured yet;
do not push/publish without the user's authorization. Update this file when the
architecture, setup, configuration or integration contract changes.

## Enterprise accounts (v0.2)

`accounts.py` owns private profile metadata, native Claude auth adapter and
single-use handoff plans. `accounts_ui.py` delivers `ui/accounts.lua` to the live
interface without changing its layout or granting capabilities. See docs/ACCOUNTS.md.
Default data: ~/.local/share/thurbox-loop/accounts; CLI --accounts-dir overrides it.
Local account sessions explicitly select tmux and check its effective server/
session environment, using public version socket metadata. Only CLAUDE_CONFIG_DIR is scoped; native Claude owns credentials. Never read/copy
credential files or weaken managed policies. Refuse conflicting provider/auth env.
Handoff requires a stopped source, pinned identity and a native compatibility
probe for the exact Claude executable. Bootstrap a native fork once, then create
the Thurbox session with --resume UUID. Never persist --agent-arg --resume PATH:
Thurbox replays those flags on restart and would reset the destination context.
Probe text is synthetic; actual account tests require human SSO. Do not claim a
cross-organization test passed without it. UI actions require user-granted run
and program capabilities; never edit ui.json trust. Run plugin check after every
live pane edit. Test accounts with unittest discover -s tests -p test_accounts.py.

Opt-in account integration: `python3.11 examples/accounts_live_smoke.py
--thurbox-cli /path/to/thurbox-cli` (one shell line). Uses synthetic native-agent
fixtures with real Thurbox/tmux; never implies Enterprise SSO was verified.
