"""Integration tests for the real backends. They SKIP cleanly when the drivers or the
containers aren't present (e.g. under system python with no venv), so the suite stays
green everywhere; run under the venv with Docker up to actually exercise them."""
import os
import unittest

from vfa.schemas import KBChunk

OS_URL = os.environ.get("OPENSEARCH_URL", "http://localhost:9200")
PG_URL = os.environ.get("POSTGRES_URL", "postgresql://voicefaq:voicefaq@localhost:55432/voicefaq")

KB = [
    KBChunk(type="faq", question="When will my refund come?",
            canonical_answer="Refunds to UPI reach you within 1 business day."),
    KBChunk(type="faq", question="What are the fees for using UPI?",
            canonical_answer="UPI payments are free for customers."),
]


def _os_ok() -> bool:
    try:
        from vfa.retrieval.opensearch_store import OpenSearchLexical
        return OpenSearchLexical(OS_URL).health()
    except Exception:
        return False


def _pg_ok() -> bool:
    try:
        from vfa.retrieval.pgvector_store import PgVectorSemantic
        s = PgVectorSemantic(PG_URL)
        ok = s.health()
        s.close()
        return ok
    except Exception:
        return False


@unittest.skipUnless(_os_ok(), "OpenSearch not reachable")
class TestOpenSearchLexical(unittest.TestCase):
    def test_index_and_search(self):
        from vfa.retrieval.opensearch_store import OpenSearchLexical
        s = OpenSearchLexical(OS_URL, index="vfa_faq_test")   # isolated from a running server
        s.index(KB)
        hits = s.search("when will my refund come", 5)
        self.assertTrue(hits)
        self.assertEqual(hits[0].chunk_id, KB[0].chunk_id)
        self.assertTrue(0.0 <= hits[0].score <= 1.0)


@unittest.skipUnless(_pg_ok(), "pgvector not reachable")
class TestPgVectorSemantic(unittest.TestCase):
    def test_index_and_search(self):
        from vfa.retrieval.pgvector_store import PgVectorSemantic
        s = PgVectorSemantic(PG_URL, table="kb_vectors_test")   # isolated from a running server
        s.index(KB)
        hits = s.search("when will my refund come", 5)
        self.assertTrue(hits)
        self.assertEqual(hits[0].chunk_id, KB[0].chunk_id)
        self.assertTrue(0.0 <= hits[0].score <= 1.0)
        s.close()


if __name__ == "__main__":
    unittest.main()
