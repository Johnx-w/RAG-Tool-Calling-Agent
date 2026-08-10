"""Load Markdown and PDF into Document objects."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pymupdf

from src.config import ROOT
from src.rag.models import Document

SKIP_NAMES = {"readme.md"}


def file_content_hash(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()[:16]


def _rel_source(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_markdown(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"空 Markdown 文件: {path}")
    source = _rel_source(path)
    doc_id = f"md:{source}"
    ch = file_content_hash(path)
    return [
        Document(
            text=text,
            doc_id=doc_id,
            source=source,
            file_type="md",
            metadata={"content_hash": ch, "file_type": "md"},
        )
    ]


def load_pdf(path: Path) -> list[Document]:
    source = _rel_source(path)
    ch = file_content_hash(path)
    docs: list[Document] = []
    with pymupdf.open(path) as pdf:
        if pdf.page_count == 0:
            raise ValueError(f"PDF 无页面: {path}")
        for i, page in enumerate(pdf, start=1):
            text = page.get_text("text") or ""
            text = text.strip()
            if not text:
                continue
            docs.append(
                Document(
                    text=text,
                    doc_id=f"pdf:{source}:p{i}",
                    source=source,
                    file_type="pdf",
                    metadata={
                        "content_hash": ch,
                        "file_type": "pdf",
                        "page": str(i),
                    },
                )
            )
    if not docs:
        raise ValueError(f"PDF 无文本层（可能是扫描件，MVP 不做 OCR）: {path}")
    return docs


def load_path(path: Path) -> list[Document]:
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".md":
        if path.name.lower() in SKIP_NAMES:
            return []
        return load_markdown(path)
    if suffix == ".pdf":
        return load_pdf(path)
    raise ValueError(f"不支持的文件类型: {suffix}")


def iter_files(directory: Path, extensions: list[str]) -> list[Path]:
    directory = directory.resolve()
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    files: list[Path] = []
    for p in sorted(directory.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            if p.name.lower() in SKIP_NAMES:
                continue
            files.append(p)
    return files


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
