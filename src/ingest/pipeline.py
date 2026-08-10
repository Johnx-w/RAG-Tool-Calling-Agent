"""Ingest pipeline: load → chunk → embed → upsert (+ BM25 sync)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config import ROOT, get_config, get_settings
from src.ingest.loaders import iter_files, load_path
from src.rag.bm25 import Bm25Store
from src.rag.chunking import chunk_documents
from src.rag.embeddings import Embedder
from src.rag.retriever import _bm25_path
from src.rag.vectorstore import VectorStore

# 评估语料白名单，避免 data/sample 里额外 PDF 污染评测
SAMPLE_ALLOW = {
    "ml_optimizers.md",
    "alphacore7_overview.md",
    "alphacore7_overview.pdf",
    "hr_kpi_q3.md",
}


@dataclass
class IngestReport:
    files: list[str]
    documents: int
    chunks: int
    skipped: list[str]
    errors: list[str]


def ingest_paths(paths: list[Path], *, reset_sources: bool = True) -> IngestReport:
    settings = get_settings()
    cfg = get_config()
    chunk_cfg = cfg.get("chunking", {})
    emb_cfg = cfg.get("embedding", {})

    embedder = Embedder(settings)
    store = VectorStore(
        persist_dir=settings.resolved_chroma_path(),
        embedding_model=settings.embedding_model,
    )
    bm25 = Bm25Store(_bm25_path())

    all_docs = []
    files_ok: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []
    replaced_sources: set[str] = set()

    for path in paths:
        try:
            docs = load_path(path)
            if not docs:
                skipped.append(str(path))
                continue
            source = docs[0].source
            if reset_sources:
                store.delete_by_source(source)
                replaced_sources.add(source)
            all_docs.extend(docs)
            files_ok.append(source)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{path}: {e}")

    chunks = chunk_documents(
        all_docs,
        chunk_size=int(chunk_cfg.get("chunk_size", 512)),
        chunk_overlap=int(chunk_cfg.get("chunk_overlap", 64)),
        md_split_by_heading=bool(chunk_cfg.get("md_split_by_heading", True)),
    )
    embeddings = embedder.embed_documents(
        [c.text for c in chunks],
        batch_size=int(emb_cfg.get("batch_size", 16)),
    )
    n = store.upsert_chunks(chunks, embeddings)
    bm25.upsert_chunks(chunks, replace_sources=replaced_sources or None)
    return IngestReport(
        files=files_ok,
        documents=len(all_docs),
        chunks=n,
        skipped=skipped,
        errors=errors,
    )


def ingest_directory(directory: Path | None = None) -> IngestReport:
    cfg = get_config()
    ingest_cfg = cfg.get("ingest", {})
    rel = directory or Path(ingest_cfg.get("sample_dir", "data/sample"))
    directory = rel if rel.is_absolute() else ROOT / rel
    exts = ingest_cfg.get("supported_extensions", [".md", ".pdf"])
    files = iter_files(directory, exts)

    sample_dir = (ROOT / ingest_cfg.get("sample_dir", "data/sample")).resolve()
    if directory.resolve() == sample_dir:
        files = [f for f in files if f.name in SAMPLE_ALLOW]

    return ingest_paths(files)
