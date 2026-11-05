"""Wire the orchestrator.

- build_offline(): pure in-memory + fakes (tests, zero infra).
- build_auto():    use OpenSearch / pgvector when reachable, else fall back to in-memory.
                   Every backend init is guarded — an unreachable or broken backend logs a
                   warning and degrades to in-memory rather than crashing (reliability first).
"""
from __future__ import annotations

import logging

from .ab.switch import ABSwitch
from .config import Settings
from .embed.embedder import Embedder, FakeEmbedder
from .escalation import CallbackTicketWriter
from .grounding.guard import GroundingGuard
from .llm.base import FakeSynthesizer, Synthesizer
from .orchestrator.turn import Orchestrator
from .redact import PIIRedactor
from .rerank.reranker import FakeReranker, Reranker
from .retrieval.base import Retriever
from .retrieval.inmemory import InMemoryLexical, InMemoryVector
from .schemas import KBChunk
from .shadow.logger import ShadowLogger
from .stt.base import FakeTranscriber
from .tts.base import FakeTTS
from .tts.cache import AudioCache

log = logging.getLogger("vfa.factory")


def _assemble(settings: Settings, chunks: list[KBChunk], lexical: Retriever, semantic: Retriever,
              reranker: Reranker, synthesizer: Synthesizer | None, tts, presynth_top_n: int) -> Orchestrator:
    lexical.index(chunks)
    semantic.index(chunks)

    audio_cache = AudioCache(settings.audio_dir, tts)
    # pre-synthesize ONLY voice-eligible FAQ chunks (short, no card digits) — these are the
    # only ones the triple-lock will serve verbatim on early-exit.
    for c in [c for c in chunks if c.type == "faq" and c.early_exit_eligible][:presynth_top_n]:
        audio_cache.presynthesize(c.chunk_id, c.answer)

    return Orchestrator(
        settings=settings, transcriber=FakeTranscriber(), redactor=PIIRedactor(),
        lexical=lexical, semantic=semantic, reranker=reranker,
        synthesizer=synthesizer or FakeSynthesizer(), guard=GroundingGuard(nli=None),
        ab=ABSwitch(settings), audio_cache=audio_cache, tts=tts,
        escalation=CallbackTicketWriter("./data/tickets.log"),
        shadow=ShadowLogger(settings.shadow_db),
        chunk_answers={c.chunk_id: c.answer for c in chunks},
    )


def build_offline(settings: Settings, chunks: list[KBChunk], *,
                  synthesizer: Synthesizer | None = None, presynth_top_n: int = 50) -> Orchestrator:
    embedder = FakeEmbedder()
    return _assemble(settings, chunks, InMemoryLexical(), InMemoryVector(embedder),
                     FakeReranker(), synthesizer, FakeTTS(), presynth_top_n)


def _make_synth(settings: Settings) -> tuple[Synthesizer, str]:
    if settings.groq_api_key:
        try:
            from .llm.groq_llm import GroqSynthesizer
            return GroqSynthesizer(settings.groq_api_key, settings.groq_model), f"Groq({settings.groq_model})"
        except Exception as e:
            log.warning("Groq init failed (%s) — falling back to FakeSynthesizer", e)
    return FakeSynthesizer(), "FakeSynthesizer"


def _make_tts(settings: Settings):
    if settings.use_real_tts and settings.elevenlabs_api_key and settings.elevenlabs_voice_id:
        try:
            from .tts.elevenlabs import ElevenLabsTTS
            return (ElevenLabsTTS(settings.elevenlabs_api_key, settings.elevenlabs_voice_id,
                                  settings.elevenlabs_model_id), "ElevenLabs(real)")
        except Exception as e:
            log.warning("ElevenLabs init failed (%s) — falling back to FakeTTS", e)
    return FakeTTS(), "FakeTTS"


def _make_embedder(settings: Settings) -> tuple[Embedder, str]:
    if settings.use_real_models:
        try:
            from .embed.embedder import BGELocalEmbedder
            emb = BGELocalEmbedder(settings.embedding_model)
            return emb, f"BGE({settings.embedding_model},{emb.dim}d)"
        except Exception as e:
            log.warning("BGE embedder load failed (%s) — falling back to FakeEmbedder", e)
    return FakeEmbedder(), "FakeEmbedder(256d)"


def _make_reranker(settings: Settings) -> tuple[Reranker, str]:
    if settings.use_real_models:
        try:
            from .rerank.reranker import BGEReranker
            return BGEReranker(settings.reranker_model), f"BGEReranker({settings.reranker_model})"
        except Exception as e:
            log.warning("BGE reranker load failed (%s) — falling back to FakeReranker", e)
    return FakeReranker(), "FakeReranker"


def _make_lexical(settings: Settings) -> tuple[Retriever, str]:
    if settings.opensearch_url:
        try:
            from .retrieval.opensearch_store import OpenSearchLexical
            store = OpenSearchLexical(settings.opensearch_url)
            if store.health():
                return store, f"OpenSearch({settings.opensearch_url})"
            log.warning("OpenSearch not healthy at %s — falling back to in-memory lexical",
                        settings.opensearch_url)
        except Exception as e:  # driver missing / connection error / anything
            log.warning("OpenSearch init failed (%s) — falling back to in-memory lexical", e)
    return InMemoryLexical(), "InMemoryLexical"


def _make_semantic(settings: Settings, embedder: Embedder) -> tuple[Retriever, str]:
    if settings.postgres_url:
        try:
            from .retrieval.pgvector_store import PgVectorSemantic
            store = PgVectorSemantic(settings.postgres_url, embedder)
            if store.health():
                return store, "pgvector(postgres)"
            log.warning("pgvector not healthy — falling back to in-memory vector")
        except Exception as e:
            log.warning("pgvector init failed (%s) — falling back to in-memory vector", e)
    return InMemoryVector(embedder), "InMemoryVector"


def build_auto(settings: Settings, chunks: list[KBChunk], *,
               synthesizer: Synthesizer | None = None,
               presynth_top_n: int = 50) -> tuple[Orchestrator, dict[str, str]]:
    embedder, emb_name = _make_embedder(settings)
    reranker, rr_name = _make_reranker(settings)
    if synthesizer is not None:
        synth, synth_name = synthesizer, "injected"
    else:
        synth, synth_name = _make_synth(settings)
    tts, tts_name = _make_tts(settings)
    lexical, lex_name = _make_lexical(settings)
    semantic, sem_name = _make_semantic(settings, embedder)
    orch = _assemble(settings, chunks, lexical, semantic, reranker, synth, tts, presynth_top_n)
    return orch, {"lexical": lex_name, "semantic": sem_name, "embedder": emb_name,
                  "reranker": rr_name, "llm": synth_name, "tts": tts_name}
