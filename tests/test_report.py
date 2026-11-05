import json
import tempfile
import unittest
from pathlib import Path

from vfa.config import Settings
from vfa.factory import build_offline
from vfa.report import build_report, load_turns
from vfa.schemas import KBChunk

KB = [KBChunk(type="faq", question="When will my refund come?",
              canonical_answer="Refunds to UPI reach you within 1 business day.")]


def _row(outcome, text, lex_ids=None, lex_scores=None):
    return {"outcome": outcome, "utterance_text": text,
            "lexical_chunk_ids": json.dumps(lex_ids or []),
            "lexical_scores": json.dumps(lex_scores or []),
            "semantic_chunk_ids": "[]", "semantic_scores": "[]"}


class TestReport(unittest.TestCase):
    def test_counts_and_answer_rate(self):
        rows = [
            _row("resolved", "when will my refund come"),
            _row("early_exit", "what are the fees"),
            _row("smalltalk", "hi"),
            _row("escalated_explicit", "get me a human"),
            _row("escalated_floor", "do you support international cards"),
            _row("escalated_floor", "international card support"),  # paraphrase -> same cluster
        ]
        rep = build_report(rows)
        self.assertEqual(rep.total_turns, 6)
        self.assertEqual(rep.answered, 2)
        self.assertEqual(rep.smalltalk, 1)
        self.assertEqual(rep.asked_for_human, 1)   # NOT counted as a KB gap
        self.assertEqual(rep.unanswered, 2)
        self.assertAlmostEqual(rep.answer_rate, 0.5)  # 2 answered / (2 + 2)

    def test_paraphrases_cluster_together(self):
        rows = [_row("escalated_floor", "do you support international cards"),
                _row("escalated_floor", "international cards do you support")]
        rep = build_report(rows)
        self.assertEqual(len(rep.clusters), 1)
        self.assertEqual(rep.clusters[0].count, 2)

    def test_nearest_chunk_surfaced(self):
        rows = [_row("escalated_grounding", "weird phrasing of refund", ["chunk_abc"], [0.42])]
        rep = build_report(rows)
        self.assertEqual(rep.clusters[0].nearest_chunk_id, "chunk_abc")
        self.assertEqual(rep.clusters[0].best_score, 0.42)

    def test_empty_db_is_clean(self):
        rep = build_report([])
        self.assertEqual(rep.unanswered, 0)
        self.assertEqual(rep.answer_rate, 0.0)
        self.assertEqual(rep.clusters, [])

    def test_end_to_end_via_shadow_log(self):
        # a real orchestrator run -> read its shadow DB -> report reflects the turns
        with tempfile.TemporaryDirectory() as d:
            s = Settings(audio_dir=str(Path(d) / "a"), shadow_db=str(Path(d) / "s.sqlite"),
                         tau_floor=0.99)  # force escalation for the unknown question
            orch = build_offline(s, KB)
            orch.handle_turn("c", 1, "hi")                                  # smalltalk
            orch.handle_turn("c", 2, "do you support crypto payments")      # escalated_floor
            rep = build_report(load_turns(s.shadow_db))
            self.assertEqual(rep.smalltalk, 1)
            self.assertEqual(rep.unanswered, 1)


if __name__ == "__main__":
    unittest.main()
