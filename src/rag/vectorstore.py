"""Chroma persistent vector store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.rag.models import Chunk, RetrievedChunk


class VectorStore:
    def __init__(
        self,
        persist_dir: Path,
        collection_name: str = "knowledge_base",
        embedding_model: str = "",
    ) -> None:
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": embedding_model or "unknown",
            },
        )

    def delete_by_source(self, source: str) -> None:
        # Chroma where filter
        try:
            self.collection.delete(where={"source": source})
        except Exception:
            # empty collection / no matches
            pass

    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError("chunks 与 embeddings 数量不一致")
        self.collection.upsert(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=embeddings,
            metadatas=[c.to_chroma_metadata() for c in chunks],
        )
        return len(chunks)

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        if top_k <= 0:
            return []
        total = self.collection.count()
        if total <= 0:
            return []
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, total),
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        hits: list[RetrievedChunk] = []
        for i, chunk_id in enumerate(ids):
            dist = float(dists[i]) if i < len(dists) else 1.0
            # cosine space in Chroma: distance ~= 1 - cos_sim
            score = 1.0 - dist
            meta: dict[str, Any] = metas[i] or {}
            hits.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    text=docs[i] or "",
                    score=score,
                    source=str(meta.get("source", "")),
                    heading_path=str(meta.get("heading_path", "")),
                    page=str(meta.get("page", "") or ""),
                    doc_id=str(meta.get("doc_id", "")),
                )
            )
        return hits

    def count(self) -> int:
        return self.collection.count()
