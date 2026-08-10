"""Vector + optional BM25 hybrid retrieval (+ optional rerank)."""

from __future__ import annotations

from pathlib import Path

from src.config import ROOT, get_config, get_settings
from src.rag.bm25 import Bm25Store
from src.rag.embeddings import Embedder
from src.rag.hybrid import maybe_rerank, rrf_fuse
from src.rag.models import RetrievedChunk
from src.rag.vectorstore import VectorStore


def _bm25_path() -> Path:
    cfg = get_config()
    paths = cfg.get("paths", {}) or {}
    rel = paths.get("bm25", "indexes/bm25/corpus.json")
    p = Path(rel)
    return p if p.is_absolute() else ROOT / p


class Retriever:
    def __init__(
        self,
        store: VectorStore | None = None,
        embedder: Embedder | None = None,
        bm25: Bm25Store | None = None,
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

        hybrid_cfg = retrieval.get("hybrid", {}) or {}
        self.hybrid_enabled = bool(hybrid_cfg.get("enabled", False))
        self.rrf_k = int(hybrid_cfg.get("rrf_k", 60))
        rerank_cfg = retrieval.get("rerank", {}) or {}
        self.rerank_enabled = bool(rerank_cfg.get("enabled", False))
        self.rerank_top_n = int(rerank_cfg.get("top_n", self.final_k))

        self.bm25 = bm25 or Bm25Store(_bm25_path())

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        k = top_k or self.final_k
        fetch_k = max(self.recall_k, k)

        qvec = self.embedder.embed_query(query)
        vec_hits = self.store.query(qvec, top_k=fetch_k)

        if self.hybrid_enabled:
            bm25_hits = self.bm25.search(query, top_k=fetch_k)
            fused = rrf_fuse([vec_hits, bm25_hits], rrf_k=self.rrf_k)
        else:
            fused = vec_hits

        if self.score_threshold is not None and not self.hybrid_enabled:
            fused = [h for h in fused if h.score >= self.score_threshold]

        candidates = fused[: max(fetch_k, k)]
        return maybe_rerank(
            query,
            candidates,
            top_n=k,
            enabled=self.rerank_enabled,
        )
