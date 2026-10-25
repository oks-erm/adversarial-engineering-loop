"""Credential-free smoke run with real code, failing tests, repair and reports."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thurbox_loop.adversarial import Adversarial
from thurbox_loop.debate import Debate
from thurbox_loop.runtime import run_checks


class ScriptedDebater:
    def __init__(self, name, prefix, opponent):
        self.name, self.prefix, self.opponent = name, prefix, opponent
        self.phase = 0

    def run(self, *, prompt, cwd, mode, schema):
        replies = [
            dict(position="A bounded state machine fits", recommendation="Use a persisted state machine",
                 arguments=["The lifecycle is fixed and small"], assumptions=["No dynamic graph mutation"],
                 risks=["Recovery needs explicit checkpoints"], change_my_mind=["A dynamic graph is required"]),
            dict(challenges=[dict(id=self.prefix + "-001", claim="Checkpoint recovery needs definition",
                 evidence="A crash can occur between two stages", impact="An interrupted run cannot continue",
                 question="Which states can be resumed safely?")]),
            dict(responses=[dict(challenge_id=self.opponent + "-001", decision="ACCEPT",
                 reason="Atomic checkpoints are required", updated_position="Persist every explicit transition")]),
            dict(decision_key="persisted-state-machine", recommendation="Use a persisted state machine",
                 strongest_argument="A fixed lifecycle does not need graph mutation", remaining_risk="Resume semantics",
                 confidence=0.9, agreements=["Atomic state persistence is necessary"], disagreements=[],
                 open_questions=["Experiment: interrupt at each state and verify recoverability before adding resume"])]
        value = replies[self.phase]
        self.phase += 1
        return value


class DemoBuilder:
    name = "Claude (fake)"

    def __init__(self):
        self.calls = 0

    def run(self, *, prompt, cwd, mode, schema):
        self.calls += 1
        code = "def normalize(values):\n    return [v.strip() for v in values]\n"
        responses = []
        if self.calls > 1:
            code = "def normalize(values):\n    if values is None:\n        return []\n    return [v.strip() for v in values]\n"
            responses = [dict(finding_id=identifier, decision="ACCEPTED",
                              evidence="Added None handling; configured regression checks exercise it",
                              action="Return an empty list for None") for identifier in ["C-001", "CHECK-001"]]
        (cwd / "solution.py").write_text(code)
        return dict(changes=["Implemented normalize"], validation=["Objective checks run by orchestrator"],
                    assumptions=["None represents absent input"], responses=responses)


class DemoAdversary:
    name = "Codex (fake)"

    def __init__(self, checks):
        self.checks, self.calls = checks, 0

    def run(self, *, prompt, cwd, mode, schema):
        self.calls += 1
        checks = run_checks(self.checks, cwd)
        failed = any(check["status"] != "PASS" for check in checks)
        findings = [dict(id="C-001", severity="HIGH", category="Input validation",
                        claim="normalize(None) crashes", evidence=checks[0]["stderr"],
                        reproduction="Run test_solution.NormalizeTests.test_absent", expected="[]",
                        observed="TypeError")] if failed else []
        assessments = [] if self.calls == 1 else [dict(finding_id=identifier, status="RESOLVED",
            evidence="All regression tests pass when independently rerun") for identifier in ["C-001", "CHECK-001"]]
        return dict(verdict="CHANGES_REQUIRED" if failed else "SATISFIED", findings=findings,
                    assessments=assessments, summary="Independent regression checks executed", blocked_reason="None")


def smoke(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    repo = output / "repository"
    repo.mkdir()
    (repo / ".gitignore").write_text("__pycache__/\n")
    (repo / "test_solution.py").write_text(
        "import unittest\nfrom solution import normalize\n\nclass NormalizeTests(unittest.TestCase):\n"
        "    def test_absent(self): self.assertEqual(normalize(None), [])\n"
        "    def test_empty(self): self.assertEqual(normalize([]), [])\n"
        "    def test_values(self): self.assertEqual(normalize([' a ']), ['a'])\n")
    (repo / "solution.py").write_text("# Implementation pending\n")
    for args in [["init", "-q"], ["config", "user.name", "Smoke"],
                 ["config", "user.email", "smoke@example.invalid"], ["add", "."],
                 ["commit", "-qm", "baseline"]]:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    debate = Debate(ScriptedDebater("Claude (fake)", "a", "b"), ScriptedDebater("Codex (fake)", "b", "a"),
                    output / "debate", repo)
    debated = debate.run("Use a graph framework or a deterministic state machine?",
                         context="Two fixed workflows with atomic state persistence",
                         criteria=["Simplicity", "Bounded execution"], constraints=["No third LLM judge"])
    worktree = output / "worktree"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-b", "adversarial/smoke",
                    str(worktree)], check=True, capture_output=True)
    checks = [[sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_solution.py", "-v"]]
    loop = Adversarial(DemoBuilder(), DemoAdversary(checks), output / "adversarial", worktree,
                       checks=lambda cwd: run_checks(checks, cwd),
                       worktree=dict(branch="adversarial/smoke", path=str(worktree)))
    built = loop.run("Implement normalize: strip strings and return [] for None or empty input.")
    assert debated["outcome"] == "CONSENSUS"
    assert built["outcome"] == "PASS" and built["rounds"] == 2
    assert all(finding["status"] == "RESOLVED" for finding in built["findings"].values())
    return dict(debate=debated["outcome"], adversarial=built["outcome"], attacks=built["rounds"],
                worktree=str(worktree), reports=[str(output / "debate/DEBATE_REPORT.md"),
                                                str(output / "adversarial/ADVERSARIAL_REPORT.md")])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = args.output or Path(tempfile.mkdtemp(prefix="thurbox-smoke-parent-")) / "run"
    print(json.dumps(smoke(target.resolve()), indent=2))
