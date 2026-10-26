"""User CLI: configuration is trusted executable input; models never supply checks."""

from __future__ import annotations

import argparse
import math
import sys
import tomllib
import uuid
from pathlib import Path

from .adversarial import Adversarial, git
from .core import dumps, redact
from .debate import Debate
from .runtime import normalize_commands, run_checks
from .thurbox import Thurbox, ThurboxAgent


def positive(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be positive and finite")
    return number


def rounds(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return number


def load_config(path: Path) -> list[list[str]]:
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    try:
        commands = config.get("adversarial", {}).get("checks", {}).get("commands", [])
    except AttributeError as error:
        raise ValueError("expected [adversarial.checks] commands configuration") from error
    return normalize_commands(commands)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="thurbox-loop", description="Debate decisions or adversarially build and review code.")
    subs = root.add_subparsers(dest="workflow", required=True)
    for name, help_text in [("debate", "Four bounded decision rounds"), ("adversarial", "Build, attack and repair until satisfied")]:
        command = subs.add_parser(name, help=help_text)
        command.add_argument("task", help="Question or implementation task")
        command.add_argument("--repo", type=Path, default=Path.cwd())
        command.add_argument("--output", type=Path, help="New run directory; never overwritten")
        command.add_argument("--thurbox-cli", default="thurbox-cli", help="Thurbox CLI executable path")
        command.add_argument("--agent-timeout", type=positive, default=600)
        if name == "debate":
            command.add_argument("--agent-a", default="claude")
            command.add_argument("--agent-b", default="codex")
            command.add_argument("--context", default="", help="Project context text")
            command.add_argument("--criterion", action="append", default=[])
            command.add_argument("--constraint", action="append", default=[])
        else:
            command.add_argument("--builder", default="claude")
            command.add_argument("--adversary", default="codex")
            command.add_argument("--max-rounds", type=rounds, default=5)
            command.add_argument("--base-ref", default="HEAD", help="Committed base for the isolated worktree")
            command.add_argument("--config", type=Path, help="Trusted TOML; default REPO/.thurbox/loop.toml")
            command.add_argument("--check", action="append", default=[], help="Trusted command; argv quoting supported, no shell operators")
            command.add_argument("--check-timeout", type=positive, default=600)
    return root


def main(argv: list[str] | None = None) -> int:
    command_parser = parser()
    args = command_parser.parse_args(argv)
    repo = args.repo.resolve()
    if not repo.is_dir() or not args.task.strip():
        command_parser.error("repo must exist and task must not be empty")
    identifier = uuid.uuid4().hex[:16]
    output = (args.output or repo / ".thurbox" / args.workflow / identifier).resolve()
    if output.exists():
        command_parser.error("output directory already exists; choose a new path")
    checks = []
    try:
        if args.workflow == "adversarial":
            config = args.config or repo / ".thurbox/loop.toml"
            if args.config or config.exists():
                checks = load_config(config)
            checks += normalize_commands(args.check)
            base = git(repo, "rev-parse", "--verify", "--end-of-options", args.base_ref + "^{commit}").strip()
    except (OSError, ValueError, RuntimeError) as error:
        command_parser.error(redact(str(error)))
    thurbox = Thurbox()
    thurbox.command = [args.thurbox_cli]
    agent = lambda name: ThurboxAgent(name, thurbox, timeout=args.agent_timeout)
    workflow = None
    try:
        if args.workflow == "debate":
            workflow = Debate(agent(args.agent_a), agent(args.agent_b), output, repo)
            thurbox.journal = output / "sessions.json"
            result = workflow.run(args.task, context=args.context, criteria=args.criterion, constraints=args.constraint)
            report = output / "DEBATE_REPORT.md"
        else:
            workflow = Adversarial(agent(args.builder), agent(args.adversary), output, repo,
                max_rounds=args.max_rounds, checks=lambda cwd: run_checks(checks, cwd, timeout=args.check_timeout))
            thurbox.journal = output / "sessions.json"
            try:
                worktree = thurbox.create_worktree(repo, identifier, base=base)
            except Exception as error:
                workflow.task = args.task
                workflow.append_log("Worktree setup failed", {"error": str(error)})
                workflow.store.fail(error)
                workflow.report()
                raise
            workflow.cwd = Path(worktree["path"])
            workflow.worktree = worktree
            result = workflow.run(args.task)
            report = output / "ADVERSARIAL_REPORT.md"
        summary = {key: result[key] for key in ["state", "outcome", "rounds", "final_verdict", "worktree", "final_commit", "reason"] if key in result}
        summary["report"] = str(report)
        print(redact(dumps(summary)))
        return 0 if result["state"] == "COMPLETE" else 3
    except (Exception, KeyboardInterrupt) as error:
        print(redact(f"{type(error).__name__}: {error}\nRun evidence: {output}"), file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 1


if __name__ == "__main__":
    raise SystemExit(main())
