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

    def test_lexical_variant_below_support_escalates_unanswerable(self):
        with tempfile.TemporaryDirectory() as d:
            # explicit lexical arm: BM25 support can't clear a 0.99 bar -> escalate
            s = self._settings(d, ab_variant="lexical", tau_bm25=0.99, tau_floor=0.0, tau_answerable=0.99)
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

    def test_explicit_human_with_trailing_punctuation(self):
        # regression: "human?" must still be detected as an explicit human request
        with tempfile.TemporaryDirectory() as d:
            orch = build_offline(self._settings(d), KB)
            r = orch.handle_turn("c", 1, "can I talk to a human?")
            self.assertEqual(r.outcome, "escalated_explicit")

    def test_greeting_is_smalltalk_not_escalation(self):
        # a bare "hi" must get a conversational reply, never a KB-miss escalation
        with tempfile.TemporaryDirectory() as d:
            orch = build_offline(self._settings(d, tau_floor=0.99), KB)
            r = orch.handle_turn("c", 1, "hi there")
            self.assertEqual(r.outcome, "smalltalk")
            self.assertEqual(r.served_path, "smalltalk")
            self.assertIn("Ana", r.response or "")

    def test_bot_question_answered_not_escalated_to_human(self):
        # "are you a human?" is an identity question -> disclosure, NOT a human handoff
        with tempfile.TemporaryDirectory() as d:
            orch = build_offline(self._settings(d), KB)
            r = orch.handle_turn("c", 1, "are you a human?")
            self.assertEqual(r.outcome, "smalltalk")

    def test_card_numbers_are_never_spoken(self):
        # regression: a chunk with card digits must not be served verbatim on any path
        with tempfile.TemporaryDirectory() as d:
            kb = [KBChunk(type="faq", question="do you have test cards",
                          canonical_answer="Test cards: Visa 4386289407660153 and Mastercard 5104015555555558.")]
            s = self._settings(d, ab_variant="lexical", tau_bm25=0.1, tau_floor=0.0,
                               tau_answerable=0.0, tau_rerank=0.0)
            orch = build_offline(s, kb)
            r = orch.handle_turn("c", 1, "do you have test cards for integration")
            self.assertTrue(r.outcome.startswith("escalated"))
            self.assertNotIn("4386289407660153", r.response or "")


if __name__ == "__main__":
    unittest.main()
