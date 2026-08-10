"""Hybrid fusion (RRF) and optional API rerank."""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

from src.config import ROOT
from src.rag.models import RetrievedChunk


def rrf_fuse(
    ranked_lists: list[list[RetrievedChunk]],
    *,
    rrf_k: int = 60,
) -> list[RetrievedChunk]:
    scores: dict[str, float] = {}
    payload: dict[str, RetrievedChunk] = {}
    for hits in ranked_lists:
        for rank, hit in enumerate(hits, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            # keep richer metadata; prefer first seen text
            if hit.chunk_id not in payload:
                payload[hit.chunk_id] = hit
    ordered_ids = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
    fused: list[RetrievedChunk] = []
    for cid in ordered_ids:
        h = payload[cid]
        fused.append(
            RetrievedChunk(
                chunk_id=h.chunk_id,
                text=h.text,
                score=scores[cid],
                source=h.source,
                heading_path=h.heading_path,
                page=h.page,
                doc_id=h.doc_id,
            )
        )
    return fused


def maybe_rerank(
    query: str,
    hits: list[RetrievedChunk],
    *,
    top_n: int,
    enabled: bool,
) -> list[RetrievedChunk]:
    if not enabled or not hits:
        return hits[:top_n]

    load_dotenv(ROOT / ".env")
    cohere_key = os.getenv("COHERE_API_KEY", "").strip()
    jina_key = os.getenv("JINA_API_KEY", "").strip()

    docs = [h.text for h in hits]
    try:
        if cohere_key:
            return _rerank_cohere(query, hits, docs, top_n, cohere_key)
        if jina_key:
            return _rerank_jina(query, hits, docs, top_n, jina_key)
    except Exception:
        # fail open: keep fused order
        return hits[:top_n]
    return hits[:top_n]


def _rerank_cohere(
    query: str,
    hits: list[RetrievedChunk],
    docs: list[str],
    top_n: int,
    api_key: str,
) -> list[RetrievedChunk]:
    url = "https://api.cohere.com/v2/rerank"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": "rerank-multilingual-v3.0",
        "query": query,
        "documents": docs,
        "top_n": min(top_n, len(docs)),
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
    results = data.get("results") or []
    out: list[RetrievedChunk] = []
    for item in results:
        idx = int(item["index"])
        h = hits[idx]
        out.append(
            RetrievedChunk(
                chunk_id=h.chunk_id,
                text=h.text,
                score=float(item.get("relevance_score", h.score)),
                source=h.source,
                heading_path=h.heading_path,
                page=h.page,
                doc_id=h.doc_id,
            )
        )
    return out[:top_n]


def _rerank_jina(
    query: str,
    hits: list[RetrievedChunk],
    docs: list[str],
    top_n: int,
    api_key: str,
) -> list[RetrievedChunk]:
    url = "https://api.jina.ai/v1/rerank"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "jina-reranker-v2-base-multilingual",
        "query": query,
        "documents": docs,
        "top_n": min(top_n, len(docs)),
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
    results = data.get("results") or []
    out: list[RetrievedChunk] = []
    for item in results:
        idx = int(item["index"])
        h = hits[idx]
        out.append(
            RetrievedChunk(
                chunk_id=h.chunk_id,
                text=h.text,
                score=float(item.get("relevance_score", h.score)),
                source=h.source,
                heading_path=h.heading_path,
                page=h.page,
                doc_id=h.doc_id,
            )
        )
    return out[:top_n]
