import tempfile
import unittest
from pathlib import Path

from vfa.config import Settings
from vfa.factory import build_offline
from vfa.llm.base import FabricatingSynthesizer
from vfa.schemas import KBChunk


KB = [
    KBChunk(type="faq", question="When will my refund come?",
            canonical_answer="Refunds to UPI reach you within 1 business day and cards within 5 to 7 business days."),
    KBChunk(type="faq", question="What are the fees for using UPI?",
            canonical_answer="UPI payments to merchants and individuals are free for customers."),
]


class TestOrchestrator(unittest.TestCase):
    def _settings(self, d, **kw):
        base = dict(audio_dir=str(Path(d) / "audio"), shadow_db=str(Path(d) / "s.sqlite"))
        base.update(kw)
        return Settings(**base)

    def test_early_exit_on_exact_question(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._settings(d, ab_variant="auto", tau_bm25=0.5, tau_floor=0.0)
            orch = build_offline(s, KB)
            r = orch.handle_turn("c", 1, "When will my refund come?")
            self.assertEqual(r.outcome, "early_exit")
            self.assertTrue(r.gate.early_exit)

    def test_explicit_human_escalates(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._settings(d)
            orch = build_offline(s, KB)
            r = orch.handle_turn("c", 1, "please connect me to a human agent")
            self.assertEqual(r.outcome, "escalated_explicit")

    def test_below_floor_escalates(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._settings(d, tau_floor=0.99)      # nothing can clear the floor
            orch = build_offline(s, KB)
            r = orch.handle_turn("c", 1, "random unrelated query about weather")
            self.assertEqual(r.outcome, "escalated_floor")

    def test_grounding_failure_escalates(self):
        with tempfile.TemporaryDirectory() as d:
            # force the semantic (LLM) path; never early-exit; never floor; always answerable
            s = self._settings(d, ab_variant="semantic", tau_bm25=0.99, tau_floor=0.0, tau_rerank=0.0)
            orch = build_offline(s, KB, synthesizer=FabricatingSynthesizer())
            r = orch.handle_turn("c", 1, "when do refunds arrive")
            self.assertEqual(r.outcome, "escalated_grounding")

    def test_weak_retrieval_escalates_unanswerable(self):
        with tempfile.TemporaryDirectory() as d:
            # reranker relevance can't clear a 0.99 bar -> escalate, never a wrong answer
            s = self._settings(d, ab_variant="semantic", tau_bm25=0.99, tau_floor=0.0, tau_rerank=0.99)
            orch = build_offline(s, KB)
            r = orch.handle_turn("c", 1, "totally unrelated gibberish tokens")
            self.assertEqual(r.outcome, "escalated_unanswerable")

    def test_shadow_row_written_per_turn(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._settings(d, tau_bm25=0.5, tau_floor=0.0)
            orch = build_offline(s, KB)
            orch.handle_turn("c", 1, "When will my refund come?")
            orch.handle_turn("c", 2, "What are the fees for using UPI?")
            self.assertEqual(orch.shadow.count(), 2)


if __name__ == "__main__":
    unittest.main()
