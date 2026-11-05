"""Integration test for the real BGE embedder. Skips unless sentence-transformers is
installed (i.e. runs under the 3.12 models venv, not the stdlib core). Downloads the
bge-small model on first run."""
import unittest


def _st_ok() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_st_ok(), "sentence-transformers not installed")
class TestBGEEmbedder(unittest.TestCase):
    def test_dim_and_semantic_similarity(self):
        from vfa.embed.embedder import BGELocalEmbedder, cosine
        e = BGELocalEmbedder("BAAI/bge-small-en-v1.5")
        self.assertEqual(e.dim, 384)
        q = e.embed("when will my refund arrive")
        para = e.embed("how long until I get my money back")        # paraphrase
        other = e.embed("what is the merchant discount rate for cards")  # unrelated
        # a real embedder ranks the paraphrase above the unrelated sentence
        self.assertGreater(cosine(q, para), cosine(q, other))


if __name__ == "__main__":
    unittest.main()
