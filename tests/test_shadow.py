import tempfile
import unittest
from pathlib import Path

from vfa.schemas import ShadowRow
from vfa.shadow.logger import ShadowLogger


def _row():
    return ShadowRow(
        call_id="c", turn_id=1, ts=1.0, active_variant="auto", served_path="lexical",
        utterance_text="hi", outcome="resolved", gate_early_exit=True, gate_reason="ok",
        lexical_chunk_ids=["a"], lexical_scores=[0.9], lexical_candidate="ans", lexical_latency_ms=1.0,
        semantic_chunk_ids=["a"], semantic_scores=[0.8], semantic_candidate="ans2", semantic_latency_ms=2.0,
        grounding_lexical_passed=True, grounding_semantic_passed=None,
        total_latency_ms=5.0, filler_played=False,
    )


class TestShadowLogger(unittest.TestCase):
    def test_write_and_count(self):
        with tempfile.TemporaryDirectory() as d:
            log = ShadowLogger(str(Path(d) / "shadow.sqlite"))
            log.write(_row())
            self.assertEqual(log.count(), 1)
            log.write(_row())          # same PK -> replace, still 1
            self.assertEqual(log.count(), 1)
            log.close()


if __name__ == "__main__":
    unittest.main()
