"""Thin wrapper around the OpenAI client (Replit AI Integrations proxy).

No API key required from the user — auto-provisioned env vars handle auth.
"""
import asyncio
import json
import os
import hashlib
from typing import Any, AsyncIterator
from openai import OpenAI, AsyncOpenAI

_MODEL = "gpt-4o-mini"


def _client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL"),
        api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "dummy"),
    )


def _async_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL"),
        api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "dummy"),
    )


def _chat_json_sync(prompt: str, system: str, max_tokens: int) -> dict:
    try:
        resp = _client().chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system + " Respond with strictly valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as e:
        # Hard failure shouldn't crash the agent — return an error envelope
        return {"_error": str(e)}


async def chat_json(prompt: str, system: str = "You are a helpful sales strategist.", max_tokens: int = 1500) -> dict:
    """Call the model and parse a JSON object from the response.

    The underlying OpenAI client is synchronous, so we run it on a worker
    thread via ``asyncio.to_thread`` to avoid blocking the FastAPI event
    loop while the request is in flight. This keeps the rest of the API
    responsive while a strategy is being generated.
    """
    return await asyncio.to_thread(_chat_json_sync, prompt, system, max_tokens)


def _chat_text_sync(prompt: str, system: str, max_tokens: int) -> str:
    try:
        resp = _client().chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[LLM error: {e}]"


async def chat_text(prompt: str, system: str = "You are a helpful sales strategist.", max_tokens: int = 1000) -> str:
    return await asyncio.to_thread(_chat_text_sync, prompt, system, max_tokens)


def deterministic_embedding(text_in: str, dim: int = 1536) -> list[float]:
    """Generate a deterministic 384-dim 'embedding' from text using SHA256.

    The Replit AI Integrations OpenAI proxy does not expose the embeddings
    API. We use a hash-based pseudo-embedding so pgvector similarity search
    still works for demoing pattern recognition. Distances are not as
    meaningful as real embeddings, but related strings still cluster.
    """
    # Take repeated hashes of the input to seed a deterministic float vector
    seed_bytes = b""
    h = hashlib.sha256(text_in.encode()).digest()
    while len(seed_bytes) < dim * 4:
        seed_bytes += h
        h = hashlib.sha256(h).digest()
    out = []
    for i in range(dim):
        chunk = seed_bytes[i * 4 : i * 4 + 4]
        # Map to [-1, 1]
        val = int.from_bytes(chunk, "big") / 2**32
        out.append(val * 2 - 1)
    # Normalise
    norm = sum(v * v for v in out) ** 0.5 or 1.0
    return [v / norm for v in out]
