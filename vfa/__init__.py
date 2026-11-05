"""Voice FAQ Agent for Payments — POC package.

Offline-first: the core turn loop (retrieval, triple-lock gate, grounding guard,
A/B switch, shadow log, orchestrator) runs with no cloud keys and no Docker, using
in-memory retrieval and fake STT/LLM/TTS. Real adapters (Deepgram/Groq/ElevenLabs/
OpenSearch/pgvector) implement the same interfaces and switch on when available.
"""

__version__ = "0.1.0"
