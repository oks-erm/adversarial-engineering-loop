import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import FakeAgent


def build(responses=None):
    return dict(changes=["Implemented task"], validation=["builder claim only"],
                assumptions=["Existing API preserved"], responses=responses or [])


def finding(identifier="C-001"):
    return dict(id=identifier, severity="HIGH", category="Correctness", claim="Empty input crashes",
                evidence="test_empty_input fails", reproduction="Call with empty list",
                expected="Empty result", observed="Exception")


def attack(verdict="SATISFIED", findings=None, assessments=None):
    return dict(verdict=verdict, findings=findings or [], assessments=assessments or [],
                summary="Adversarial inspection complete", blocked_reason="None")


def response(identifier="C-001", decision="ACCEPTED"):
    return dict(finding_id=identifier, decision=decision, evidence="Regression test",
                action="Fixed empty-input handling")


def assessment(identifier="C-001", status="RESOLVED"):
    return dict(finding_id=identifier, status=status, evidence="Regression test now passes")


class AdversarialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        for args in [["init", "-q"], ["config", "user.name", "Test"],
                     ["config", "user.email", "test@example.invalid"]]:
            subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)
        (self.repo / "code.txt").write_text("baseline\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "baseline"], check=True)

    def run_loop(self, attacks, builds=None, checks=None, max_rounds=5):
        from thurbox_loop.adversarial import Adversarial
        builder = FakeAgent("builder", builds or [build()])
        adversary = FakeAgent("reviewer", attacks)
        loop = Adversarial(builder, adversary, self.root / "run", self.repo,
                           checks=checks or (lambda cwd: []), max_rounds=max_rounds,
                           worktree={"branch": "adversarial/test", "path": str(self.repo)})
        result = loop.run("Implement safe empty input")
        return result, builder, adversary

    def test_first_attack_is_independent_and_report_has_worktree(self):
        result, builder, reviewer = self.run_loop([attack()])
        self.assertEqual(result["outcome"], "PASS_WITH_WARNINGS")
        self.assertNotIn("builder claim only", reviewer.calls[0]["prompt"])
        self.assertIn("Implement safe empty input", reviewer.calls[0]["prompt"])
        self.assertEqual(builder.calls[0]["mode"], "write")
        self.assertEqual(reviewer.calls[0]["mode"], "read_only")
        report = (self.root / "run/ADVERSARIAL_REPORT.md").read_text()
        for text in ["SATISFIED", "adversarial/test", str(self.repo), "Changed Files", "Validation"]:
            self.assertIn(text, report)

    def test_repair_then_satisfied(self):
        result, builder, reviewer = self.run_loop([
            attack("CHANGES_REQUIRED", [finding()]), attack(assessments=[assessment()])],
            [build(), build([response()])])
        self.assertEqual(result["rounds"], 2)
        self.assertEqual(result["findings"]["C-001"]["status"], "RESOLVED")
        self.assertIn("C-001", builder.calls[1]["prompt"])
        self.assertIn("additional defects", reviewer.calls[1]["prompt"])
        log = (self.root / "run/ADVERSARIAL_LOG.md").read_text()
        for text in ["Attack 1", "Repair 1", "Attack 2", "ACCEPTED", "SATISFIED"]:
            self.assertIn(text, log)

    def test_new_finding_after_repair_and_rejected_finding(self):
        result, _, _ = self.run_loop([
            attack("CHANGES_REQUIRED", [finding()]),
            attack("CHANGES_REQUIRED", [finding("C-002")], [assessment()]),
            attack(assessments=[assessment(), assessment("C-002")])],
            [build(), build([response(decision="REJECTED")]), build([response("C-002")])])
        self.assertEqual(result["rounds"], 3)
        self.assertEqual(len(result["findings"]), 2)
        self.assertEqual(result["findings"]["C-001"]["response"]["decision"], "REJECTED")

    def test_blocked_verdict(self):
        result, _, _ = self.run_loop([attack("BLOCKED")])
        self.assertEqual(result["state"], "BLOCKED")

    def test_max_rounds(self):
        result, _, _ = self.run_loop([attack("CHANGES_REQUIRED", [finding()])], max_rounds=1)
        self.assertEqual(result["state"], "MAX_ROUNDS_REACHED")

    def test_objective_failure_outranks_satisfied(self):
        check = dict(command=["test"], status="FAIL", exit_code=1, stdout="failure", stderr="")
        result, _, _ = self.run_loop([attack()], checks=lambda cwd: [check], max_rounds=1)
        self.assertEqual(result["outcome"], "MAX_ROUNDS_REACHED")
        self.assertIn("CHECK-001", result["findings"])
        self.assertEqual(result["final_verdict"], "SATISFIED")

    def test_passing_objective_check_allows_pass(self):
        check = dict(command=["test"], status="PASS", exit_code=0, stdout="ok", stderr="")
        result, _, _ = self.run_loop([attack()], checks=lambda cwd: [check])
        self.assertEqual(result["outcome"], "PASS")
        report = (self.root / "run/ADVERSARIAL_REPORT.md").read_text()
        self.assertIn('| ["test"] | PASS |', report)

    def test_invalid_verdict_and_crash_persist_failed_report(self):
        for bad in [attack("MAYBE"), RuntimeError("agent crashed")]:
            with self.subTest(bad=bad):
                self.root = self.root / "next"
                self.root.mkdir()
                with self.assertRaises((ValueError, RuntimeError)):
                    self.run_loop([bad])
                state = json.loads((self.root / "run/state.json").read_text())
                self.assertEqual(state["state"], "FAILED")
                self.assertTrue((self.root / "run/ADVERSARIAL_REPORT.md").exists())

    def test_missing_repair_response_is_failure(self):
        with self.assertRaisesRegex(ValueError, "finding"):
            self.run_loop([attack("CHANGES_REQUIRED", [finding()])], [build(), build()])

    def test_satisfied_with_open_findings_is_malformed(self):
        with self.assertRaises(ValueError):
            self.run_loop([attack(findings=[finding()])])

    def test_untracked_code_visible_in_first_attack(self):
        (self.repo / "new.py").write_text("def broken(): return 1 / 0\n")
        _, _, reviewer = self.run_loop([attack()])
        self.assertIn("def broken():", reviewer.calls[0]["prompt"])
        self.assertIn("new.py", reviewer.calls[0]["prompt"])

    def test_repeated_identical_evidence_blocks(self):
        result, _, _ = self.run_loop([
            attack("CHANGES_REQUIRED", [finding()]),
            attack("CHANGES_REQUIRED", assessments=[assessment(status="OPEN")]),
            attack("CHANGES_REQUIRED", assessments=[assessment(status="OPEN")])],
            [build(), build([response()]), build([response()])])
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("progress", result["reason"])

    def test_reviewer_must_account_for_previous_findings(self):
        with self.assertRaisesRegex(ValueError, "assessment"):
            self.run_loop([attack("CHANGES_REQUIRED", [finding()]), attack()],
                          [build(), build([response()])])

    def test_reviewer_modifying_code_cannot_approve_its_own_changes(self):
        from thurbox_loop.adversarial import Adversarial

        class MutatingReviewer(FakeAgent):
            def run(agent, **kwargs):
                (self.repo / "code.txt").write_text("tampered during review\n")
                return super(MutatingReviewer, agent).run(**kwargs)

        loop = Adversarial(FakeAgent("builder", [build()]), MutatingReviewer("reviewer", [attack()]),
                           self.root / "mutation", self.repo, checks=lambda cwd: [])
        with self.assertRaisesRegex(ValueError, "changed during"):
            loop.run("Implement task")

    def test_check_timing_jitter_does_not_hide_no_progress(self):
        calls = 0

        def checks(cwd):
            nonlocal calls
            calls += 1
            return [dict(command=["test"], status="PASS", exit_code=0, stdout="ok", stderr="", duration=calls)]

        result, _, _ = self.run_loop([
            attack("CHANGES_REQUIRED", [finding()]),
            attack("CHANGES_REQUIRED", assessments=[assessment(status="OPEN")]),
            attack("CHANGES_REQUIRED", assessments=[assessment(status="OPEN")])],
            [build(), build([response()]), build([response()])], checks=checks)
        self.assertEqual(result["state"], "BLOCKED")

    def test_untracked_binary_and_executable_mode_changes_reject_verdict(self):
        from thurbox_loop.adversarial import Adversarial

        for case in ["binary", "mode"]:
            with self.subTest(case=case):
                target = self.repo / (case + ".bin")
                target.write_bytes(b"\x80" if case == "binary" else b"#!/bin/sh\nexit 0\n")
                target.chmod(0o644)

                class MutatingReviewer(FakeAgent):
                    def run(agent, **kwargs):
                        if case == "binary":
                            target.write_bytes(b"\x81")
                        else:
                            target.chmod(0o755)
                        return super(MutatingReviewer, agent).run(**kwargs)

                loop = Adversarial(FakeAgent("builder", [build()]), MutatingReviewer("reviewer", [attack()]),
                                   self.root / ("mutation-" + case), self.repo, checks=lambda cwd: [])
                with self.assertRaisesRegex(ValueError, "changed during"):
                    loop.run("Implement task")

    def test_builder_crash_preserves_partial_change_evidence(self):
        from thurbox_loop.adversarial import Adversarial

        class CrashingBuilder(FakeAgent):
            def run(agent, **kwargs):
                (self.repo / "partial.py").write_text("# Partial implementation\n")
                raise RuntimeError("builder crashed")

        loop = Adversarial(CrashingBuilder("builder", []), FakeAgent("reviewer", []),
                           self.root / "crash", self.repo, checks=lambda cwd: [])
        with self.assertRaisesRegex(RuntimeError, "builder crashed"):
            loop.run("Implement task")
        state = json.loads((self.root / "crash/state.json").read_text())
        self.assertEqual(state["state"], "FAILED")
        self.assertIn("partial.py", state["changed_files"])
