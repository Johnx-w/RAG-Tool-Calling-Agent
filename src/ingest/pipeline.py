"""Ingest pipeline: load → chunk → embed → upsert."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config import ROOT, get_config, get_settings
from src.ingest.loaders import iter_files, load_path
from src.rag.chunking import chunk_documents
from src.rag.embeddings import Embedder
from src.rag.vectorstore import VectorStore


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

    all_docs = []
    files_ok: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for path in paths:
        try:
            docs = load_path(path)
            if not docs:
                skipped.append(str(path))
                continue
            if reset_sources:
                # one source path may yield multiple page docs; delete once per file
                store.delete_by_source(docs[0].source)
            all_docs.extend(docs)
            files_ok.append(docs[0].source)
        except Exception as e:  # noqa: BLE001 — collect per-file errors for CLI
            errors.append(f"{path}: {e}")

    chunks = chunk_documents(
        all_docs,
        chunk_size=int(chunk_cfg.get("chunk_size", 512)),
        chunk_overlap=int(chunk_cfg.get("chunk_overlap", 64)),
        md_split_by_heading=bool(chunk_cfg.get("md_split_by_heading", True)),
    )
    embeddings = embedder.embed_documents(
        [c.text for c in chunks],
        batch_size=int(emb_cfg.get("batch_size", 64)),
    )
    n = store.upsert_chunks(chunks, embeddings)
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
    return ingest_paths(files)
