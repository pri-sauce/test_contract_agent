# """
# llm.py — Async Ollama client with parallel request support.

# Two clients:
#   llm        — sync (backwards compat, used for metadata/summary)
#   async_llm  — async (used for parallel clause review)

# Direct httpx calls to Ollama REST API instead of the ollama SDK.
# The SDK serialises requests — httpx lets us fire all 46 clauses concurrently.
# """

# import asyncio
# import json
# from typing import Optional, Generator

# import httpx
# import ollama
# from loguru import logger

# from core.config import config

# # ── Ollama REST endpoints ──────────────────────────────────────────────────
# _BASE   = config.OLLAMA_BASE_URL.rstrip("/")
# _CHAT   = f"{_BASE}/api/chat"

# # ── Parallelism knob ───────────────────────────────────────────────────────
# # Ollama on a 95GB card with a 14B model (fp16 ~28GB) can handle multiple
# # concurrent requests through its internal queue.
# # 10 workers keeps GPU saturated without OOM or queue saturation.
# PARALLEL_WORKERS: int = int(getattr(config, "PARALLEL_WORKERS", 10))

# # ── Shared async HTTP client (created once, reused across all requests) ────
# _async_client: Optional[httpx.AsyncClient] = None


# def _get_async_client() -> httpx.AsyncClient:
#     global _async_client
#     if _async_client is None or _async_client.is_closed:
#         _async_client = httpx.AsyncClient(
#             timeout=httpx.Timeout(300.0, connect=10.0),
#             limits=httpx.Limits(max_connections=20, max_keepalive_connections=20),
#         )
#     return _async_client


# # ------------------------------------------------------------------
# # Async LLM Client
# # ------------------------------------------------------------------

# class AsyncLLMClient:
#     """
#     Async LLM client for parallel clause review.
#     Uses httpx directly so multiple requests fly concurrently.
#     """

#     def __init__(self):
#         self.primary_model = config.PRIMARY_MODEL
#         self.fast_model    = config.FAST_MODEL
#         # Semaphore: caps concurrent in-flight requests to Ollama
#         self._sem = asyncio.Semaphore(PARALLEL_WORKERS)

#     async def generate(
#         self,
#         prompt: str,
#         system: Optional[str] = None,
#         model: Optional[str] = None,
#         temperature: float = 0.1,
#         max_tokens: int = 2048,
#     ) -> str:
#         """Async single-turn generation. Returns complete response string."""
#         use_model = model or self.primary_model

#         messages = []
#         if system:
#             messages.append({"role": "system", "content": system})
#         messages.append({"role": "user", "content": prompt})

#         payload = {
#             "model":   use_model,
#             "messages": messages,
#             "stream":  False,
#             "options": {
#                 "temperature": temperature,
#                 "num_predict": max_tokens,
#             },
#         }

#         async with self._sem:
#             client = _get_async_client()
#             try:
#                 resp = await client.post(_CHAT, json=payload)
#                 resp.raise_for_status()
#                 data = resp.json()
#                 return data["message"]["content"]
#             except Exception as e:
#                 logger.error(f"Async generation failed ({use_model}): {e}")
#                 raise

#     async def fast_generate(self, prompt: str, system: Optional[str] = None) -> str:
#         return await self.generate(
#             prompt=prompt,
#             system=system,
#             model=self.fast_model,
#             temperature=0.0,
#             max_tokens=512,
#         )


# # ------------------------------------------------------------------
# # Sync LLM Client (unchanged — used for metadata/summary/RAG)
# # ------------------------------------------------------------------

# class LLMClient:
#     """
#     Sync LLM client. Unchanged from original.
#     Used for: metadata extraction, executive summary, embeddings.
#     Clause review now goes through AsyncLLMClient.
#     """

#     def __init__(self):
#         self.client         = ollama.Client(host=config.OLLAMA_BASE_URL)
#         self.primary_model  = config.PRIMARY_MODEL
#         self.fast_model     = config.FAST_MODEL
#         self.embedding_model = config.EMBEDDING_MODEL

#     def check_connection(self) -> bool:
#         try:
#             models    = self.client.list()
#             available = [m.model for m in models.models]
#             logger.info(f"Ollama connected. Available models: {available}")
#             required = {self.primary_model, self.fast_model}
#             missing  = required - set(available)
#             if missing:
#                 logger.warning(f"Missing models: {missing}")
#                 return False
#             logger.success("All required models available.")
#             return True
#         except Exception as e:
#             logger.error(f"Cannot connect to Ollama at {config.OLLAMA_BASE_URL}: {e}")
#             return False

#     def generate(
#         self,
#         prompt: str,
#         system: Optional[str] = None,
#         model: Optional[str] = None,
#         temperature: float = 0.1,
#         max_tokens: int = 2048,
#     ) -> str:
#         use_model = model or self.primary_model
#         messages  = []
#         if system:
#             messages.append({"role": "system", "content": system})
#         messages.append({"role": "user", "content": prompt})
#         try:
#             response = self.client.chat(
#                 model=use_model,
#                 messages=messages,
#                 options={"temperature": temperature, "num_predict": max_tokens},
#             )
#             return response.message.content
#         except Exception as e:
#             logger.error(f"Generation failed ({use_model}): {e}")
#             raise

#     def fast_generate(self, prompt: str, system: Optional[str] = None) -> str:
#         return self.generate(
#             prompt=prompt, system=system,
#             model=self.fast_model,
#             temperature=0.0, max_tokens=512,
#         )

#     def stream(
#         self,
#         prompt: str,
#         system: Optional[str] = None,
#         model: Optional[str] = None,
#         temperature: float = 0.1,
#     ) -> Generator[str, None, None]:
#         use_model = model or self.primary_model
#         messages  = []
#         if system:
#             messages.append({"role": "system", "content": system})
#         messages.append({"role": "user", "content": prompt})
#         for chunk in self.client.chat(
#             model=use_model, messages=messages,
#             stream=True, options={"temperature": temperature},
#         ):
#             if chunk.message.content:
#                 yield chunk.message.content

#     def embed(self, text: str) -> list[float]:
#         try:
#             response = self.client.embeddings(
#                 model=self.embedding_model, prompt=text,
#             )
#             return response.embedding
#         except Exception as e:
#             logger.error(f"Embedding failed: {e}")
#             raise

#     def embed_batch(self, texts: list[str]) -> list[list[float]]:
#         return [self.embed(t) for t in texts]


# # Singletons
# llm       = LLMClient()
# async_llm = AsyncLLMClient()


"""
llm.py - Async + Sync Ollama client with num_ctx tuning.

Key optimizations:
- num_ctx=2048  for triage calls (tiny output, short clauses)
- num_ctx=2048 for deep review calls (still covers all clauses)
- Semaphore matches OLLAMA_NUM_PARALLEL exactly
- Direct httpx to Ollama REST - no SDK serialization overhead
"""

import asyncio
from typing import Optional, Generator

import httpx
import ollama
from loguru import logger

from core.config import config

_BASE  = config.OLLAMA_BASE_URL.rstrip("/")
_CHAT  = f"{_BASE}/api/chat"
_EMBED = f"{_BASE}/api/embeddings"

# Shared async client - one connection pool for all requests
_async_client: Optional[httpx.AsyncClient] = None

def _get_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None or _async_client.is_closed:
        _async_client = httpx.AsyncClient(
            timeout=httpx.Timeout(600.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=config.PARALLEL_WORKERS + 4,
                max_keepalive_connections=config.PARALLEL_WORKERS + 4,
            ),
        )
    return _async_client


class AsyncLLMClient:
    """
    Async Ollama client using httpx directly.
    Semaphore = PARALLEL_WORKERS so we never send more requests
    than Ollama can process in parallel (OLLAMA_NUM_PARALLEL).
    """

    def __init__(self):
        self.primary_model = config.PRIMARY_MODEL
        self.fast_model    = config.FAST_MODEL
        self._sem = asyncio.Semaphore(config.PARALLEL_WORKERS)

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        num_ctx: int = 2048,
    ) -> str:
        use_model = model or self.primary_model
        messages  = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model":   use_model,
            "messages": messages,
            "stream":  False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx":     num_ctx,
                "num_batch":   1024,
                "num_gpu":     99,
                "keep_alive":  -1,
            },
        }

        async with self._sem:
            client = _get_client()
            try:
                resp = await client.post(_CHAT, json=payload)
                resp.raise_for_status()
                return resp.json()["message"]["content"]
            except Exception as e:
                logger.error(f"Async generation failed ({use_model}): {e!r}")
                import traceback; logger.error(traceback.format_exc())
                raise

    async def triage(self, prompt: str, system: Optional[str] = None) -> str:
        """Ultra-fast triage call - tiny context, tiny output."""
        return await self.generate(
            prompt=prompt,
            system=system,
            temperature=0.0,
            max_tokens=80,
            num_ctx=2048,  # 0.8B models need more context headroom
        )

    async def fast_generate(self, prompt: str, system: Optional[str] = None) -> str:
        return await self.generate(
            prompt=prompt,
            system=system,
            temperature=0.0,
            max_tokens=512,
            num_ctx=2048,
        )


class LLMClient:
    """Sync Ollama client - used for metadata, summary, embeddings."""

    def __init__(self):
        self.client          = ollama.Client(host=config.OLLAMA_BASE_URL)
        self.primary_model   = config.PRIMARY_MODEL
        self.fast_model      = config.FAST_MODEL
        self.embedding_model = config.EMBEDDING_MODEL

    def check_connection(self) -> bool:
        try:
            models    = self.client.list()
            available = [m.model for m in models.models]
            logger.info(f"Ollama connected. Models: {available}")
            required  = {self.primary_model, self.fast_model}
            missing   = required - set(available)
            if missing:
                logger.warning(f"Missing models: {missing}")
                logger.warning(f"Run: ollama pull {' && ollama pull '.join(missing)}")
                return False
            logger.success("All required models available.")
            return True
        except Exception as e:
            logger.error(f"Cannot connect to Ollama: {e}")
            return False

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        num_ctx: int = 2048,
    ) -> str:
        use_model = model or self.primary_model
        messages  = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            response = self.client.chat(
                model=use_model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "num_ctx":     num_ctx,
                    "num_batch":   1024,
                    "num_gpu":     99,
                    "keep_alive":  -1,
                },
            )
            return response.message.content
        except Exception as e:
            logger.error(f"Generation failed ({use_model}): {e}")
            raise

    def fast_generate(self, prompt: str, system: Optional[str] = None) -> str:
        return self.generate(
            prompt=prompt, system=system,
            model=self.fast_model,
            temperature=0.0, max_tokens=512,
            num_ctx=2048,
        )

    def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Generator[str, None, None]:
        use_model = model or self.primary_model
        messages  = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        for chunk in self.client.chat(
            model=use_model, messages=messages,
            stream=True,
            options={"temperature": temperature, "num_ctx": 2048, "num_batch": 1024, "num_gpu": 99, "keep_alive": -1},
        ):
            if chunk.message.content:
                yield chunk.message.content

    def embed(self, text: str) -> list[float]:
        try:
            return self.client.embeddings(
                model=self.embedding_model, prompt=text,
            ).embedding
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


llm       = LLMClient()
async_llm = AsyncLLMClient()