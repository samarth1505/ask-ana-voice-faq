import unittest

from vfa.grounding.guard import GroundingGuard
from vfa.schemas import RetrievedChunk


class TestGroundingGuard(unittest.TestCase):
    def setUp(self):
        self.guard = GroundingGuard()
        self.ctx = [RetrievedChunk("c1", 0.9,
                    "Refunds to UPI reach you within 1 business day and cards within 5 to 7 business days.")]

    def test_grounded_response_passes(self):
        r = self.guard.check("Refunds reach UPI within 1 business day.", self.ctx)
        self.assertTrue(r.passed, r.flagged_claims)

    def test_fabricated_number_fails(self):
        r = self.guard.check("Your refund will arrive in exactly 99 business days.", self.ctx)
        self.assertFalse(r.passed)
        self.assertIn("number:99", r.flagged_claims)

    def test_ungrounded_entity_fails(self):
        r = self.guard.check("You can use NEFT for this refund.", self.ctx)
        self.assertFalse(r.passed)
        self.assertIn("entity:neft", r.flagged_claims)


if __name__ == "__main__":
    unittest.main()
