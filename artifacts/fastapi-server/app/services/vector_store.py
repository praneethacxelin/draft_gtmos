"""ChromaDB-backed vector store for the GTM Factory.

Why ChromaDB (and not pgvector)?
  - pgvector needs a compiled native Postgres extension, which is painful on
    Windows. ChromaDB is a pure-Python embedded vector DB that persists to a
    local directory — no extension, no server.

What it powers:
  - Semantic ICP-fit scoring: each account/contact is compared against the
    strategy's ICP profile to produce a real similarity score (0..1) that
    feeds lead scoring, instead of a crude title-presence heuristic.
  - Pattern memory: learned conversion patterns are embedded so future
    similar patterns can be recognised.

Embeddings:
  - Prefer ChromaDB's built-in local sentence-transformer model
    (``DefaultEmbeddingFunction``) for *real* semantic embeddings — no API key
    required. If that model can't load (e.g. offline / missing onnxruntime),
    we fall back to the deterministic SHA-based pseudo-embedding from
    ``app.llm`` so the rest of the app keeps working (similarity is weaker but
    nothing breaks).

Everything here is defensive: if ChromaDB itself can't be imported or the
store can't be initialised, every method degrades to a no-op / ``None`` and
callers fall back to their existing heuristics.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

log = logging.getLogger("gtm.vector")

# Collections
_ICP_COLLECTION = "icp_profiles"
_ACCOUNT_COLLECTION = "accounts"
_PATTERN_COLLECTION = "pattern_clusters"
_LEARNING_COLLECTION = "gtm_learnings"


class _VectorStore:
    """Lazily-initialised singleton wrapper around a persistent Chroma client."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._initialised = False
        self._enabled = False
        self._client = None
        self._embed_fn = None  # callable(list[str]) -> list[list[float]] | None

    # ---- lifecycle -------------------------------------------------------

    def _ensure(self) -> bool:
        """Initialise the client on first use. Returns True if usable."""
        if self._initialised:
            return self._enabled
        with self._lock:
            if self._initialised:
                return self._enabled
            self._initialised = True
            try:
                import chromadb

                path = os.environ.get(
                    "CHROMA_DIR",
                    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "chroma_db"),
                )
                path = os.path.abspath(path)
                os.makedirs(path, exist_ok=True)
                self._client = chromadb.PersistentClient(path=path)
                self._embed_fn = self._load_embedder()
                self._enabled = True
                log.info("ChromaDB vector store ready at %s", path)
            except Exception as exc:  # pragma: no cover - environment dependent
                log.warning("ChromaDB unavailable, vector features disabled: %s", exc)
                self._enabled = False
            return self._enabled

    def _load_embedder(self):
        """Return a callable that embeds a list of strings, or None."""
        try:
            from chromadb.utils import embedding_functions

            ef = embedding_functions.DefaultEmbeddingFunction()
            # Warm up / validate it actually runs.
            _ = ef(["warmup"])
            log.info("Using ChromaDB DefaultEmbeddingFunction (semantic)")
            return ef
        except Exception as exc:
            log.warning(
                "DefaultEmbeddingFunction unavailable (%s); "
                "falling back to deterministic embeddings",
                exc,
            )
            try:
                from app.llm import deterministic_embedding

                def _det(texts: list[str]) -> list[list[float]]:
                    return [deterministic_embedding(t) for t in texts]

                return _det
            except Exception:
                return None

    def _embed(self, texts: list[str]) -> Optional[list[list[float]]]:
        if not self._embed_fn:
            return None
        try:
            out = self._embed_fn(texts)
            # Coerce to plain Python floats: embedding functions return numpy
            # float32 arrays which both Chroma's validator and JSON storage
            # reject.
            return [[float(x) for x in v] for v in out]
        except Exception as exc:
            log.warning("embedding failed: %s", exc)
            return None

    def _collection(self, name: str):
        try:
            # We always pass embeddings explicitly, so no embedding function
            # is needed on the collection itself.
            return self._client.get_or_create_collection(name=name)
        except Exception as exc:
            log.warning("could not open collection %s: %s", name, exc)
            return None

    @property
    def enabled(self) -> bool:
        return self._ensure()

    # ---- ICP profile -----------------------------------------------------

    def upsert_icp(self, strategy_id: str, text: str) -> Optional[list[float]]:
        """Store/replace the ICP embedding for a strategy. Returns the vector."""
        if not self._ensure() or not text:
            return None
        col = self._collection(_ICP_COLLECTION)
        if col is None:
            return None
        vec = self._embed([text])
        if not vec:
            return None
        try:
            col.upsert(
                ids=[strategy_id],
                embeddings=vec,
                documents=[text[:4000]],
                metadatas=[{"strategy_id": strategy_id}],
            )
            return vec[0]
        except Exception as exc:
            log.warning("upsert_icp failed: %s", exc)
            return None

    def icp_fit(self, strategy_id: str, account_text: str) -> Optional[float]:
        """Return semantic similarity (0..1) between an account and the ICP.

        Uses cosine distance from Chroma; ``similarity = 1 - distance/2`` keeps
        the result in [0, 1] for cosine space.
        """
        if not self._ensure() or not account_text:
            return None
        col = self._collection(_ICP_COLLECTION)
        if col is None:
            return None
        vec = self._embed([account_text])
        if not vec:
            return None
        try:
            res = col.query(
                query_embeddings=vec,
                n_results=1,
                where={"strategy_id": strategy_id},
            )
            dists = (res or {}).get("distances") or []
            if not dists or not dists[0]:
                return None
            distance = float(dists[0][0])
            similarity = max(0.0, min(1.0, 1.0 - distance / 2.0))
            return similarity
        except Exception as exc:
            log.warning("icp_fit query failed: %s", exc)
            return None

    # ---- pattern memory --------------------------------------------------

    def upsert_pattern(self, strategy_id: str, pattern_id: str, text: str) -> Optional[list[float]]:
        if not self._ensure() or not text:
            return None
        col = self._collection(_PATTERN_COLLECTION)
        if col is None:
            return None
        vec = self._embed([text])
        if not vec:
            return None
        try:
            col.upsert(
                ids=[pattern_id],
                embeddings=vec,
                documents=[text[:2000]],
                metadatas=[{"strategy_id": strategy_id}],
            )
            return vec[0]
        except Exception as exc:
            log.warning("upsert_pattern failed: %s", exc)
            return None

    def delete_patterns(self, strategy_id: str) -> None:
        if not self._ensure():
            return
        col = self._collection(_PATTERN_COLLECTION)
        if col is None:
            return
        try:
            col.delete(where={"strategy_id": strategy_id})
        except Exception as exc:
            log.warning("delete_patterns failed: %s", exc)

    # ---- centralized learnings ------------------------------------------

    def add_learning(
        self,
        learning_id: str,
        text: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Embed and store a learning. Returns True if it landed in the store."""
        if not self._ensure() or not text:
            return False
        col = self._collection(_LEARNING_COLLECTION)
        if col is None:
            return False
        vec = self._embed([text])
        if not vec:
            return False
        # Chroma metadata values must be primitive (str/int/float/bool).
        meta = {"learning_id": learning_id}
        for k, v in (metadata or {}).items():
            if isinstance(v, (str, int, float, bool)) and v is not None:
                meta[k] = v
        try:
            col.upsert(
                ids=[learning_id],
                embeddings=vec,
                documents=[text[:4000]],
                metadatas=[meta],
            )
            return True
        except Exception as exc:
            log.warning("add_learning failed: %s", exc)
            return False

    def search_learnings(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """Semantic search over learnings.

        Returns a list of ``{id, document, similarity, metadata}`` sorted by
        similarity (highest first). Degrades to ``[]`` if the store is down.
        """
        if not self._ensure() or not query_text:
            return []
        col = self._collection(_LEARNING_COLLECTION)
        if col is None:
            return []
        vec = self._embed([query_text])
        if not vec:
            return []
        try:
            res = col.query(
                query_embeddings=vec,
                n_results=max(1, n_results),
                where=where or None,
            )
        except Exception as exc:
            log.warning("search_learnings failed: %s", exc)
            return []
        ids = (res or {}).get("ids") or [[]]
        docs = (res or {}).get("documents") or [[]]
        dists = (res or {}).get("distances") or [[]]
        metas = (res or {}).get("metadatas") or [[]]
        out: list[dict] = []
        for i, _id in enumerate(ids[0] if ids else []):
            distance = float(dists[0][i]) if dists and dists[0] else 1.0
            similarity = max(0.0, min(1.0, 1.0 - distance / 2.0))
            out.append({
                "id": _id,
                "document": (docs[0][i] if docs and docs[0] else None),
                "similarity": round(similarity, 4),
                "metadata": (metas[0][i] if metas and metas[0] else {}) or {},
            })
        return out

    def delete_learning(self, learning_id: str) -> None:
        if not self._ensure():
            return
        col = self._collection(_LEARNING_COLLECTION)
        if col is None:
            return
        try:
            col.delete(ids=[learning_id])
        except Exception as exc:
            log.warning("delete_learning failed: %s", exc)


# Module-level singleton
store = _VectorStore()
