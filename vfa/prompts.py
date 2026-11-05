"""Fixed spoken lines (pre-synth'd in production; design §10)."""

GREETING = ("Hi, I'm Priya, the automated assistant. This call may be recorded for "
            "quality. For your safety, please don't share card numbers, PINs, or OTPs. "
            "How can I help?")

ESCALATION_LINE = ("I'd like a human representative to take this one so you get the right "
                   "answer — someone will call you back in a few minutes.")

CSAT_PROMPT = "On a scale of 1 to 5, how helpful was that? Press a number to rate."

# caller words that mean "get me a human" (design §10/§11)
HUMAN_REQUEST_WORDS = {"agent", "human", "representative", "operator"}
