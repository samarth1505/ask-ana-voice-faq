import unittest

from vfa.ab.switch import ABSwitch
from vfa.config import Settings
from vfa.schemas import PathResult, RetrievedChunk


def _lex(top, second=0.0):
    hits = [RetrievedChunk("c1", top, "a")]
    if second:
        hits.append(RetrievedChunk("c2", second, "b"))
    return PathResult(path="lexical", retrieved=hits)


class TestABSwitch(unittest.TestCase):
    def test_forced_variants(self):
        self.assertEqual(ABSwitch(Settings(ab_variant="lexical")).select("x", _lex(0.9), None), "lexical")
        self.assertEqual(ABSwitch(Settings(ab_variant="semantic")).select("x", _lex(0.9), None), "semantic")

    def test_lexical_only_skips_semantic(self):
        self.assertTrue(ABSwitch(Settings(ab_variant="lexical_only")).skip_semantic)

    def test_auto_routes_confident_short_query_to_lexical(self):
        sw = ABSwitch(Settings(ab_variant="auto", tau_bm25=0.6))
        self.assertEqual(sw.select("what are the fees", _lex(0.95, 0.2), None), "lexical")

    def test_auto_routes_weak_query_to_semantic(self):
        sw = ABSwitch(Settings(ab_variant="auto", tau_bm25=0.6))
        self.assertEqual(sw.select("my payment seems to have some problem today", _lex(0.3, 0.25), None), "semantic")


if __name__ == "__main__":
    unittest.main()
