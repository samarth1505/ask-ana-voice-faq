import unittest

from vfa.config import Settings
from vfa.gate import evaluate_gate
from vfa.schemas import PathResult, RetrievedChunk


def _path(name, chunk_id, score, ctype="faq"):
    return PathResult(path=name, retrieved=[RetrievedChunk(chunk_id, score, "ans", ctype)])


class TestTripleLock(unittest.TestCase):
    def setUp(self):
        self.s = Settings(tau_bm25=0.6)

    def test_all_three_satisfied_early_exits(self):
        lex = _path("lexical", "c1", 0.9)
        sem = _path("semantic", "c1", 0.8)
        self.assertTrue(evaluate_gate(lex, sem, self.s).early_exit)

    def test_low_score_blocks_early_exit(self):
        lex = _path("lexical", "c1", 0.5)        # below tau
        sem = _path("semantic", "c1", 0.8)
        self.assertFalse(evaluate_gate(lex, sem, self.s).early_exit)

    def test_disagreement_blocks_early_exit(self):
        lex = _path("lexical", "c1", 0.9)
        sem = _path("semantic", "c2", 0.8)        # different top chunk
        self.assertFalse(evaluate_gate(lex, sem, self.s).early_exit)

    def test_non_faq_blocks_early_exit(self):
        lex = _path("lexical", "c1", 0.9, ctype="policy")
        sem = _path("semantic", "c1", 0.8, ctype="policy")
        self.assertFalse(evaluate_gate(lex, sem, self.s).early_exit)


if __name__ == "__main__":
    unittest.main()
