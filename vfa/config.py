"""Settings loaded from environment (and an optional .env), with safe offline defaults.

No third-party dotenv dependency — a tiny stdlib loader keeps the offline core clean.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader: KEY=VALUE lines, # comments, no interpolation."""
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        # Do not clobber values already exported in the real environment.
        os.environ.setdefault(key, val)


def _get(key: str, default: str | None = None) -> str | None:
    v = os.environ.get(key)
    return v if v not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    # --- cloud keys (absent in the POC until the demo) ---
    deepgram_api_key: str | None = None
    groq_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model_id: str = "eleven_turbo_v2_5"

    # --- local services ---
    opensearch_url: str | None = None
    postgres_url: str | None = None

    # --- local paths & toggles ---
    audio_dir: str = "./data/audio"
    transcript_dir: str = "./data/transcripts"
    shadow_db: str = "./data/shadow.sqlite"
    ab_variant: str = "auto"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"   # POC: lighter than v2-m3 (~2.3GB) on CPU
    use_real_models: bool = False                     # True -> real BGE embedder+reranker (3.12 venv)
    use_real_tts: bool = False                         # True -> real ElevenLabs TTS (SPENDS credits)

    # --- gate thresholds (operate on normalised [0,1] scores; see design §6) ---
    # NOTE: these are tuned for the in-memory POC scorer. Real OpenSearch BM25 and
    # a real cross-encoder produce different score scales, so tau MUST be re-tuned
    # per backend on the eval set before trusting the early-exit path. (design D5/R10)
    tau_bm25: float = 0.62        # early-exit lexical floor (triple-lock condition 1)
    tau_floor: float = 0.18       # below this on BOTH paths -> escalate to callback
    # answerability on the LEXICAL served path (BM25-normalised score).
    tau_answerable: float = 0.45
    # answerability on the SEMANTIC served path = the cross-encoder reranker's top score.
    # The reranker gives ~0 for "nothing matches", so a low bar reliably catches out-of-KB
    # queries. Scale differs for fake vs real models (set per-mode in load_settings).
    # ALL of tau_* are interim dials — the eval harness fits them on labelled data. (flagged)
    tau_rerank: float = 0.25
    llm_timeout_ms: int = 600     # hard LLM timeout (design §6)
    max_answer_words: int = 50    # voice-length cap (design §11)
    top_k: int = 5                # retrieval depth per path
    rerank_top_n: int = 3         # chunks handed to the LLM after rerank

    @property
    def offline(self) -> bool:
        """True when any cloud key is missing — use fakes for STT/LLM/TTS."""
        return not (self.deepgram_api_key and self.groq_api_key and self.elevenlabs_api_key)


def load_settings(dotenv: bool = True) -> Settings:
    if dotenv:
        _load_dotenv()
    _real = (_get("VFA_REAL_MODELS", "") or "").lower() in ("1", "true", "yes")
    # In real-model mode, auto-apply thresholds fit by the eval harness (if present).
    # Precedence: explicit env var > eval/tuned_thresholds.json > per-mode default.
    _tuned: dict = {}
    if _real:
        try:
            _tuned = json.loads(Path("eval/tuned_thresholds.json").read_text())
        except Exception:
            _tuned = {}

    def _th(env: str, key: str, default: float) -> float:
        return float(_get(env, str(_tuned.get(key, default))))

    return Settings(
        deepgram_api_key=_get("DEEPGRAM_API_KEY"),
        groq_api_key=_get("GROQ_API_KEY"),
        elevenlabs_api_key=_get("ELEVENLABS_API_KEY"),
        elevenlabs_voice_id=_get("ELEVENLABS_VOICE_ID"),
        elevenlabs_model_id=_get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5"),
        opensearch_url=_get("OPENSEARCH_URL"),
        postgres_url=_get("POSTGRES_URL"),
        audio_dir=_get("AUDIO_DIR", "./data/audio"),
        transcript_dir=_get("TRANSCRIPT_DIR", "./data/transcripts"),
        shadow_db=_get("SHADOW_DB", "./data/shadow.sqlite"),
        ab_variant=_get("AB_VARIANT", "auto"),
        embedding_model=_get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
        reranker_model=_get("RERANKER_MODEL", "BAAI/bge-reranker-base"),
        use_real_models=_real,
        use_real_tts=(_get("VFA_REAL_TTS", "") or "").lower() in ("1", "true", "yes"),
        tau_bm25=_th("TAU_BM25", "tau_bm25", 0.62),
        tau_rerank=_th("TAU_RERANK", "tau_rerank", 0.08 if _real else 0.25),
    )
