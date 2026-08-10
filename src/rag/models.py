"""Shared document / chunk types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    """One loaded unit (whole MD file, or one PDF page)."""

    text: str
    doc_id: str
    source: str
    file_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    chunk_id: str
    text: str
    doc_id: str
    source: str
    heading_path: str = ""
    page: str = ""
    content_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_chroma_metadata(self) -> dict[str, str | int | float | bool]:
        # Chroma metadata values must be scalars
        return {
            "doc_id": self.doc_id,
            "source": self.source,
            "heading_path": self.heading_path or "",
            "page": self.page or "",
            "content_hash": self.content_hash or "",
            "file_type": str(self.metadata.get("file_type", "")),
        }


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    source: str
    heading_path: str = ""
    page: str = ""
    doc_id: str = ""

    def header(self, index: int) -> str:
        page = self.page if self.page not in ("", "None", None) else ""
        page_part = f" | page={page}" if page else ""
        heading = self.heading_path or "(no heading)"
        return f"[{index}] file={self.source} | chapter={heading}{page_part}"
