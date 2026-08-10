"""Vector retrieval service."""

from __future__ import annotations

from src.config import get_config, get_settings
from src.rag.embeddings import Embedder
from src.rag.models import RetrievedChunk
from src.rag.vectorstore import VectorStore


class Retriever:
    def __init__(
        self,
        store: VectorStore | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        settings = get_settings()
        cfg = get_config()
        self.embedder = embedder or Embedder(settings)
        self.store = store or VectorStore(
            persist_dir=settings.resolved_chroma_path(),
            embedding_model=settings.embedding_model,
        )
        retrieval = cfg.get("retrieval", {})
        self.recall_k = int(retrieval.get("recall_k", 20))
        self.final_k = int(retrieval.get("final_k", 5))
        thr = retrieval.get("score_threshold", None)
        self.score_threshold = float(thr) if thr is not None else None

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        k = top_k or self.final_k
        # Phase 1: single-stage; use final_k (or max(recall, final) then truncate)
        fetch_k = max(self.recall_k, k)
        qvec = self.embedder.embed_query(query)
        hits = self.store.query(qvec, top_k=fetch_k)
        if self.score_threshold is not None:
            hits = [h for h in hits if h.score >= self.score_threshold]
        return hits[:k]
