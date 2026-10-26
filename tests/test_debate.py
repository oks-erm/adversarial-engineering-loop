import json
import tempfile
import unittest
from pathlib import Path

from helpers import FakeAgent, challenge, final, position, rebuttal


class DebateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_debate(self, last=None, a_replies=None):
        from thurbox_loop.debate import Debate
        a = FakeAgent("custom-a", a_replies if a_replies is not None else
                      [position("SECRET_A"), challenge("A-001"), rebuttal("B-001"), final()])
        b = FakeAgent("custom-b", [position("SECRET_B"), challenge("B-001"),
                                   rebuttal("A-001"), last or final()])
        debate = Debate(a, b, self.root / "run", self.root)
        result = debate.run("Choose an orchestrator", context="Existing service",
                            criteria=["Simplicity"], constraints=["No new dependencies"])
        return result, a, b

    def test_complete_rounds_independence_and_report(self):
        result, a, b = self.run_debate()
        self.assertEqual(result["outcome"], "CONSENSUS")
        for agent, opposing in [(a, "SECRET_B"), (b, "SECRET_A")]:
            self.assertNotIn(opposing, agent.calls[0]["prompt"])
            self.assertIn("Simplicity", agent.calls[0]["prompt"])
            self.assertIn("No new dependencies", agent.calls[0]["prompt"])
            self.assertIn("SECRET_A", agent.calls[1]["prompt"])
            self.assertIn("SECRET_B", agent.calls[1]["prompt"])
            self.assertEqual(len(agent.calls), 4)
            self.assertTrue(all(c["mode"] == "read_only" for c in agent.calls))
        state = json.loads((self.root / "run/state.json").read_text())
        self.assertEqual(state["state"], "COMPLETE")
        self.assertEqual(state["history"], ["INITIALIZED", "POSITIONING", "POSITIONS_COMPLETE",
                                          "CROSS_EXAMINATION", "REBUTTAL", "FINAL_POSITIONS",
                                          "SYNTHESIS", "COMPLETE"])
        self.assertEqual(json.loads((self.root / "run/a-position.json").read_text())["position"],
                         "SECRET_A")
        report = (self.root / "run/DEBATE_REPORT.md").read_text()
        for section in ["Question", "Context", "Decision Criteria", "Initial Position",
                        "Cross-Examination", "Rebuttals", "Final Positions", "Agreements",
                        "Disagreements", "Recommended Decision", "Remaining Risks", "Open Questions"]:
            self.assertIn(section, report)

    def test_disagreement_is_unresolved_and_both_recommendations_survive(self):
        result, _, _ = self.run_debate(final("Use LangGraph", "graph"))
        self.assertEqual(result["outcome"], "UNRESOLVED")
        report = (self.root / "run/DEBATE_REPORT.md").read_text()
        self.assertIn("Use LangGraph", report)
        self.assertIn("Use a state machine", report)
        self.assertIn("OUTCOME: UNRESOLVED", report)

    def test_equal_key_does_not_hide_different_recommendations(self):
        result, _, _ = self.run_debate(final("Use LangGraph"))
        self.assertEqual(result["outcome"], "UNRESOLVED")

    def test_rebuttal_must_cover_actual_challenges(self):
        with self.assertRaisesRegex(ValueError, "challenge"):
            self.run_debate(a_replies=[position(), challenge("A-001"), rebuttal("INVENTED")])
        self.assertEqual(json.loads((self.root / "run/state.json").read_text())["state"], "FAILED")
        self.assertTrue((self.root / "run/DEBATE_REPORT.md").exists())

    def test_crash_is_persisted_and_surfaced(self):
        with self.assertRaisesRegex(RuntimeError, "agent crashed"):
            self.run_debate(a_replies=[RuntimeError("agent crashed")])
        state = json.loads((self.root / "run/state.json").read_text())
        self.assertEqual(state["state"], "FAILED")
        self.assertIn("agent crashed", state["error"])

    def test_invalid_transition_rejected_and_run_cannot_be_overwritten(self):
        from thurbox_loop.core import Store
        store = Store(self.root / "state", "debate", {"INITIALIZED": {"POSITIONING"}})
        with self.assertRaisesRegex(ValueError, "transition"):
            store.transition("COMPLETE")
        with self.assertRaises(FileExistsError):
            Store(self.root / "state", "debate", {})

    def test_empty_or_malformed_agent_result_fails(self):
        with self.assertRaises(ValueError):
            self.run_debate(a_replies=[{}])
