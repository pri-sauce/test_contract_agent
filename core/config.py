"""
config.py - All settings hardcoded here. No .env file needed.
Change values directly in this file.
"""

import os
import subprocess
from pathlib import Path


def start_ollama():
    """
    Launch Ollama with optimal parallel settings.
    Call this once at startup before importing llm.
    If Ollama is already running, this does nothing.
    """
    import httpx
    try:
        httpx.get("http://localhost:11434", timeout=2.0)
        return  # already running
    except Exception:
        pass  # not running, start it

    env = os.environ.copy()
    env["OLLAMA_NUM_PARALLEL"]      = "4"
    env["OLLAMA_MAX_LOADED_MODELS"] = "1"

    subprocess.Popen(
        ["ollama", "serve"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait until it responds
    import time
    for _ in range(20):
        time.sleep(1)
        try:
            httpx.get("http://localhost:11434", timeout=2.0)
            return
        except Exception:
            pass


class Config:
    # --- Ollama ---
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # --- Models ---
    PRIMARY_MODEL:   str = "qwen2.5:7b-instruct-q4_K_M"
    FAST_MODEL:      str = "qwen2.5:7b-instruct-q4_K_M"
    EMBEDDING_MODEL: str = "nomic-embed-text"

    # --- Parallelism ---
    # Must match OLLAMA_NUM_PARALLEL above
    PARALLEL_WORKERS: int = 4

    # --- Two-tier triage ---
    ENABLE_TRIAGE: bool = True

    # --- Paths ---
    BASE_DIR:           Path = Path(__file__).parent.parent
    DATA_DIR:           Path = BASE_DIR / "data"
    UPLOADS_DIR:        Path = BASE_DIR / "data/uploads"
    PROCESSED_DIR:      Path = BASE_DIR / "data/processed"
    KNOWLEDGE_BASE_DIR: Path = BASE_DIR / "data/knowledge_base"
    PLAYBOOK_PATH:      Path = BASE_DIR / "data/knowledge_base/playbook.yaml"

    # --- Chunking ---
    MAX_CHUNK_TOKENS:     int = 512
    CHUNK_OVERLAP_TOKENS: int = 50

    # --- Agent ---
    RISK_THRESHOLD: str = "MEDIUM"

    # --- Logging ---
    LOG_LEVEL: str  = "INFO"
    LOG_FILE:  Path = BASE_DIR / "data/agent.log"

    @classmethod
    def ensure_dirs(cls):
        for d in [cls.DATA_DIR, cls.UPLOADS_DIR, cls.PROCESSED_DIR, cls.KNOWLEDGE_BASE_DIR]:
            d.mkdir(parents=True, exist_ok=True)


# Auto-start Ollama with correct settings when this module loads
start_ollama()

config = Config()
config.ensure_dirs()