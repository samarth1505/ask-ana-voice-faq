import unittest

from vfa.redact import PIIRedactor


class TestRedact(unittest.TestCase):
    def setUp(self):
        self.r = PIIRedactor()

    def test_card_redacted(self):
        out, hits = self.r.redact("my card is 4386 2894 0766 0153 please")
        self.assertIn("[REDACTED_NUMBER]", out)
        self.assertGreaterEqual(hits, 1)

    def test_otp_redacted(self):
        out, hits = self.r.redact("the otp is 123456")
        self.assertIn("[REDACTED_OTP]", out)
        self.assertGreaterEqual(hits, 1)

    def test_plain_text_untouched(self):
        out, hits = self.r.redact("when will my refund arrive")
        self.assertEqual(out, "when will my refund arrive")
        self.assertEqual(hits, 0)


if __name__ == "__main__":
    unittest.main()
