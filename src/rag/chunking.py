"""Chunking: Markdown-by-heading + recursive character split."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

from src.rag.models import Chunk, Document

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)\s*$")
_SEPARATORS = ["\n\n", "\n", "。", "；", " ", ""]


def _stable_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _recursive_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    def split_with(sep: str) -> list[str]:
        if sep == "":
            # hard cut
            pieces = []
            step = max(1, chunk_size - overlap)
            for i in range(0, len(text), step):
                pieces.append(text[i : i + chunk_size])
            return [p for p in pieces if p.strip()]
        return [p for p in text.split(sep) if p.strip()]

    for sep in _SEPARATORS:
        parts = split_with(sep)
        if sep == "" or len(parts) > 1:
            # merge parts greedily
            merged: list[str] = []
            buf = ""
            for part in parts:
                candidate = part if not buf else (buf + (sep if sep else "") + part)
                if len(candidate) <= chunk_size:
                    buf = candidate
                else:
                    if buf:
                        merged.append(buf)
                    if len(part) > chunk_size:
                        merged.extend(
                            _recursive_split(part, chunk_size, overlap)
                        )
                        buf = ""
                    else:
                        buf = part
            if buf:
                merged.append(buf)
            # apply overlap between merged windows when hard-cut path already handled
            if overlap > 0 and sep != "" and len(merged) > 1:
                overlapped: list[str] = []
                for i, m in enumerate(merged):
                    if i == 0:
                        overlapped.append(m)
                        continue
                    prev_tail = merged[i - 1][-overlap:]
                    overlapped.append(prev_tail + (sep if sep else "") + m)
                return overlapped
            return merged
    return [text[:chunk_size]]


def _split_markdown_by_heading(text: str) -> list[tuple[str, str]]:
    """Return list of (heading_path, section_body)."""
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []
    current_path = ""

    def flush() -> None:
        nonlocal buf, current_path
        body = "\n".join(buf).strip()
        if body:
            sections.append((current_path, body))
        buf = []

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current_path = " / ".join(t for _, t in stack)
            buf.append(line)
        else:
            buf.append(line)
    flush()
    if not sections:
        return [("", text.strip())] if text.strip() else []
    return sections


def chunk_document(
    doc: Document,
    *,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    md_split_by_heading: bool = True,
) -> list[Chunk]:
    content_hash = str(doc.metadata.get("content_hash", ""))
    page = str(doc.metadata.get("page", "") or "")
    chunks: list[Chunk] = []

    if doc.file_type == "md" and md_split_by_heading:
        sections = _split_markdown_by_heading(doc.text)
    else:
        heading = str(doc.metadata.get("heading_path", "") or "")
        sections = [(heading, doc.text)]

    for heading_path, body in sections:
        pieces = _recursive_split(body, chunk_size, chunk_overlap)
        for i, piece in enumerate(pieces):
            cid = _stable_id(doc.doc_id, heading_path, str(i), piece[:64])
            chunks.append(
                Chunk(
                    chunk_id=cid,
                    text=piece,
                    doc_id=doc.doc_id,
                    source=doc.source,
                    heading_path=heading_path,
                    page=page,
                    content_hash=content_hash,
                    metadata={"file_type": doc.file_type},
                )
            )
    return chunks


def chunk_documents(
    docs: Iterable[Document],
    *,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    md_split_by_heading: bool = True,
) -> list[Chunk]:
    out: list[Chunk] = []
    for doc in docs:
        out.extend(
            chunk_document(
                doc,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                md_split_by_heading=md_split_by_heading,
            )
        )
    return out
