"""BM25 keyword index persisted alongside Chroma."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jieba
from rank_bm25 import BM25Okapi

from src.rag.models import Chunk, RetrievedChunk

_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+|[a-zA-Z0-9_\-]+")


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    # jieba for Chinese; also keep ascii tokens
    parts = jieba.lcut(text)
    tokens: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if _TOKEN_RE.fullmatch(p) or any("\u4e00" <= ch <= "\u9fff" for ch in p):
            if len(p) >= 1:
                tokens.append(p)
    # ensure alphanumeric keywords like AlphaCore-7 survive
    tokens.extend(_TOKEN_RE.findall(text))
    return tokens


class Bm25Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, Any]] = []
        self._bm25: BM25Okapi | None = None
        self._corpus_tokens: list[list[str]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.records = []
            self._rebuild()
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.records = data.get("records", [])
        self._rebuild()

    def _save(self) -> None:
        payload = {"records": self.records}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    def _rebuild(self) -> None:
        self._corpus_tokens = [tokenize(r.get("text", "")) for r in self.records]
        if self._corpus_tokens:
            self._bm25 = BM25Okapi(self._corpus_tokens)
        else:
            self._bm25 = None

    def upsert_chunks(self, chunks: list[Chunk], *, replace_sources: set[str] | None = None) -> int:
        if replace_sources:
            self.records = [
                r for r in self.records if r.get("source") not in replace_sources
            ]
        # de-dupe by chunk id
        existing = {r["chunk_id"]: i for i, r in enumerate(self.records)}
        for c in chunks:
            row = {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "source": c.source,
                "heading_path": c.heading_path,
                "page": c.page,
                "doc_id": c.doc_id,
            }
            if c.chunk_id in existing:
                self.records[existing[c.chunk_id]] = row
            else:
                existing[c.chunk_id] = len(self.records)
                self.records.append(row)
        self._rebuild()
        self._save()
        return len(chunks)

    def search(self, query: str, top_k: int = 20) -> list[RetrievedChunk]:
        if not self._bm25 or not self.records or top_k <= 0:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        hits: list[RetrievedChunk] = []
        for i in ranked[:top_k]:
            if scores[i] <= 0:
                continue
            r = self.records[i]
            hits.append(
                RetrievedChunk(
                    chunk_id=r["chunk_id"],
                    text=r["text"],
                    score=float(scores[i]),
                    source=r.get("source", ""),
                    heading_path=r.get("heading_path", ""),
                    page=str(r.get("page", "") or ""),
                    doc_id=r.get("doc_id", ""),
                )
            )
        return hits
