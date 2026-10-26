"""Opt-in integration test with real Thurbox/tmux and controlled agents, no LLM calls."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thurbox-cli", default="thurbox-cli")
    parser.add_argument("--extension-root", type=Path,
                        help="Test an installed extension directory instead of source")
    parser.add_argument("--output", type=Path, help="New exclusive directory; artifacts/worktrees retained")
    args = parser.parse_args()
    binary = shutil.which(args.thurbox_cli)
    if binary is None:
        parser.error("Thurbox CLI executable not found")
    target = args.output or Path(tempfile.mkdtemp(prefix="tbx-live-", dir="/tmp")) / "run"
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=False)
    config = target / "config"
    config.mkdir()
    os.environ["THURBOX_CONFIG_DIR"] = str(config)
    os.environ["THURBOX_DATA_DIR"] = str(target / "data")
    os.environ["THURBOX_SOCKET"] = "tbx-live-" + uuid.uuid4().hex[:12]
    # Scope these settings to this test's new configuration, never personal agents.
    (config / "settings.toml").write_text("[features]\nauto_update = false\nversion_check = false\n"
                                           "automations = false\nnotifications = false\n")
    extension = (args.extension_root or Path(__file__).resolve().parents[1]).resolve()
    sys.path.insert(0, str(extension))
    from thurbox_loop.adversarial import Adversarial
    from thurbox_loop.core import atomic_write, dumps
    from thurbox_loop.debate import Debate
    from thurbox_loop.runtime import run_checks
    from thurbox_loop.thurbox import Thurbox, ThurboxAgent
    from smoke import smoke

    tb = Thurbox([binary], journal=target / "sessions.json")
    # Older releases embed these; newer releases have no such manifests.
    for builtin in ("hooks", "ui-skill"):
        try:
            tb.call("extension", "deactivate", builtin)
        except RuntimeError as error:
            if "is not installed" not in str(error):
                raise
    registry = 'config_version = 1\ndefault = "loop-test-a"\n'
    for role in ("a", "b", "builder", "reviewer"):
        registry += ('\n[[agents]]\nname = "loop-test-' + role + '"\ncommand = ' + json.dumps(sys.executable)
                     + '\nargs = ' + json.dumps(["-u", str(Path(__file__).with_name("live_agent.py").resolve()), role]) + '\n')
    (config / "agents.toml").write_text(registry)
    smoke(target / "fixture")
    repo = target / "fixture/repository"
    agent = lambda role: ThurboxAgent("loop-test-" + role, tb, timeout=30)
    debate = Debate(agent("a"), agent("b"), target / "debate", repo)
    decision = debate.run("Use a graph framework or a persisted state machine?", criteria=["Simplicity"])
    assert decision["outcome"] == "CONSENSUS", decision
    worktree = tb.create_worktree(repo, "live-smoke")
    checks = [[sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_solution.py", "-v"]]
    loop = Adversarial(agent("builder"), agent("reviewer"), target / "adversarial", Path(worktree["path"]),
                       checks=lambda cwd: run_checks(checks, cwd), worktree=worktree)
    result = loop.run("Implement normalize: strip strings; return [] for None and empty inputs.")
    assert result["outcome"] == "PASS" and result["rounds"] == 2, result
    created = {event["id"] for event in tb.events if event["event"] == "created"}
    stopped = {event["id"] for event in tb.events if event["event"] == "stopped"}
    assert len(created) == 13 and created == stopped, tb.events
    assert Path(worktree["path"]).is_dir(), worktree
    listed = subprocess.run([binary, "session", "list", "--json"], check=True,
                            capture_output=True, text=True, timeout=30)
    actual = {session["id"] for session in json.loads(listed.stdout) if session.get("stopped")}
    assert created <= actual, "Thurbox has test sessions that are not stopped"
    tb.call("runtime", "stop")
    summary = dict(debate=decision["outcome"], adversarial=result["outcome"], rounds=result["rounds"],
                   created_sessions=len(created), stopped_sessions=len(stopped), worktree=worktree,
                   verified_stopped_sessions=len(created & actual),
                   report_directory=str(target), thurbox_version=tb.call("version"))
    atomic_write(target / "summary.json", dumps(summary) + "\n")
    print(dumps(summary))


if __name__ == "__main__":
    main()
