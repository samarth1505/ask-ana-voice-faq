import unittest

from vfa.smalltalk import classify


class TestSmallTalk(unittest.TestCase):
    def _intent(self, text):
        r = classify(text)
        return r[0] if r else None

    def test_greetings(self):
        for t in ["hi", "hello", "hey there", "hi priya", "good morning", "namaste"]:
            self.assertEqual(self._intent(t), "greeting", t)

    def test_thanks(self):
        for t in ["thanks", "thank you", "thanks so much", "thank you very much"]:
            self.assertEqual(self._intent(t), "thanks", t)

    def test_goodbye_and_closing(self):
        for t in ["bye", "goodbye", "that's all thanks", "no that's all", "i'm all good", "nothing else"]:
            self.assertEqual(self._intent(t), "goodbye", t)

    def test_wellbeing(self):
        for t in ["how are you", "how are you doing", "how's it going"]:
            self.assertEqual(self._intent(t), "wellbeing", t)

    def test_acknowledgement_and_hold(self):
        self.assertEqual(self._intent("ok"), "acknowledgement")
        self.assertEqual(self._intent("sure"), "acknowledgement")
        self.assertEqual(self._intent("hold on"), "hold")
        self.assertEqual(self._intent("just a second"), "hold")

    def test_bot_disclosure_identity_questions(self):
        for t in ["are you a bot", "are you human", "are you a real person", "is this a recording"]:
            self.assertEqual(self._intent(t), "bot_disclosure", t)

    # --- the safety properties: must NOT swallow real content or human requests ---
    def test_real_questions_fall_through(self):
        for t in ["what are your fees", "hi what are your fees", "thanks when will my refund come",
                  "how are you going to refund my money", "how do i capture a payment"]:
            self.assertIsNone(classify(t), t)

    def test_human_request_is_not_smalltalk(self):
        # these must fall through to the orchestrator's explicit-human escalation
        for t in ["connect me to a human", "i want to speak to an agent", "get me a representative"]:
            self.assertIsNone(classify(t), t)

    def test_empty(self):
        self.assertIsNone(classify(""))
        self.assertIsNone(classify("   "))


if __name__ == "__main__":
    unittest.main()
