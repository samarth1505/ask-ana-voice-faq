"""Pre-retrieval conversational layer.

Handles greetings, thanks, goodbyes, "how are you", acknowledgements / "hold on", and the
"are you a bot?" disclosure question with canned, FACT-FREE replies — so a caller who opens
with "hi" or closes with "thank you" gets a human-feeling response instead of a KB miss that
collapses to an escalation.

Safety properties (why this can't produce a wrong answer):
  1. It NEVER states a payment fact — every reply is fixed, generic chit-chat.
  2. It only fires when the utterance is PURELY conversational: after the recognised phrase
     and filler words are removed, no substantive token may remain. So "hi, what are your
     fees?" is NOT small talk — it falls straight through to retrieval, untouched.
  3. "I want an agent / connect me to a human" is NOT small talk (no identity-question form),
     so it falls through to the orchestrator's explicit-human escalation. Only the IDENTITY
     question ("are you a human/bot?") is answered here, with a disclosure line.

classify() returns (intent, reply) or None. None means "not small talk — keep going".
"""
from __future__ import annotations

import re

from .util.text import normalize

# --- canned, fact-free replies (Priya's voice) ---------------------------------
BOT_REPLY = ("I'm Priya, an automated assistant — not a person — but I'm happy to help with "
             "your payment questions, and I can connect you to a human anytime.")
WELL_REPLY = "I'm doing well, thank you for asking! What can I help you with today?"
GREET_REPLY = "Hi there! I'm Priya. What can I help you with on your payments today?"
THANK_REPLY = "You're welcome! Is there anything else I can help you with?"
BYE_REPLY = "Thanks for calling — take care, and goodbye!"
HOLD_REPLY = "Sure, take your time — I'm here when you're ready."
ACK_REPLY = "Got it. Is there anything else I can help you with?"

# --- trigger vocabularies (single tokens), highest priority first ---------------
_BYE = {"bye", "goodbye", "cya", "farewell", "adios", "ciao"}
_THANK = {"thanks", "thank", "thankyou", "thx", "ty", "cheers", "appreciate", "appreciated", "thankful"}
_GREET = {"hi", "hello", "hey", "heya", "hiya", "yo", "hai", "helo", "namaste", "greetings",
          "sup", "howdy", "hola", "morning", "afternoon", "evening"}
_HOLD = {"hold", "wait", "sec", "second", "moment", "minute", "hang"}
_ACK = {"ok", "okay", "okey", "k", "kk", "sure", "cool", "alright", "allright", "right", "yeah",
        "yep", "yup", "yes", "ya", "no", "fine", "great", "perfect", "nice", "awesome", "hmm",
        "mhm", "gotcha", "understood", "noted", "roger"}

# Non-trigger filler tokens that are allowed to co-occur without making it "substantive".
_FILLERS = {"a", "an", "the", "you", "your", "u", "i", "me", "my", "is", "this", "that", "it",
            "am", "are", "be", "to", "and", "so", "well", "then", "now", "there", "please",
            "oh", "on", "one", "just", "of", "good", "priya", "very", "much", "really", "mate"}

_PRIORITY = (
    (_BYE, "goodbye", BYE_REPLY),
    (_THANK, "thanks", THANK_REPLY),
    (_GREET, "greeting", GREET_REPLY),
    (_HOLD, "hold", HOLD_REPLY),
    (_ACK, "acknowledgement", ACK_REPLY),
)
_TRIGGERS = _BYE | _THANK | _GREET | _HOLD | _ACK
_ALLOWED = _TRIGGERS | _FILLERS

# --- phrase intents (regex). These carry their own trigger words, so after the match we
#     require the RESIDUAL (what's left) to contain no substantive token. -----------
_WORD = re.compile(r"[a-z0-9']+")
_BOT_RE = re.compile(
    r"(?:are you|r u|is this|is that|am i (?:talking|speaking) to)\s+(?:a |an )?"
    r"(?:real |actual |live )*"
    r"(?:bot|robot|human(?: being)?|person|people|machine|ai|recording|automated|computer|agent|real)")
_WELL_RE = re.compile(
    r"how'?s it going|how is it going|how are you(?:\s+(?:doing|today|going|feeling))?"
    r"|how r u|how are things|how do you do|how you doing|how are ya"
    r"|hope you(?:'?re| are) (?:well|doing well)")
_CLOSE_RE = re.compile(
    r"that'?s (?:all|it)|that is (?:all|it)|nothing else|no more questions"
    r"|i'?m (?:all )?(?:good|done|fine|set)|i am (?:all )?(?:good|done|fine|set)"
    r"|no(?:,)? (?:that'?s all|thanks|thank you)")


def _residual_empty(norm: str, m: re.Match) -> bool:
    """True if removing the matched span leaves only allowed filler/trigger tokens."""
    rest = norm[: m.start()] + " " + norm[m.end():]
    return all(t in _ALLOWED for t in _WORD.findall(rest))


def classify(text: str) -> tuple[str, str] | None:
    """Return (intent, canned_reply) if the utterance is pure small talk, else None."""
    norm = normalize(text)
    if not norm:
        return None

    # phrase intents first (they may legitimately contain their own keywords)
    for rx, intent, reply in ((_BOT_RE, "bot_disclosure", BOT_REPLY),
                              (_WELL_RE, "wellbeing", WELL_REPLY),
                              (_CLOSE_RE, "goodbye", BYE_REPLY)):
        m = rx.search(norm)
        if m and _residual_empty(norm, m):
            return (intent, reply)

    # single-token intents: fire only if EVERY token is conversational and at least one is a
    # trigger (so a real question with chit-chat words in it is never swallowed).
    toks = _WORD.findall(norm)
    if not toks or not set(toks) <= _ALLOWED:
        return None
    trig = set(toks) & _TRIGGERS
    if not trig:
        return None
    for words, intent, reply in _PRIORITY:
        if trig & words:
            return (intent, reply)
    return None
