"""Find already-indexed documents by filename (metadata catalog, not semantic RAG)."""

from __future__ import annotations

import json
from pathlib import Path

from src.config import get_settings
from src.rag.vectorstore import VectorStore


def find_indexed_file(name_query: str = "") -> str:
    """
    Look up imported documents by filename / path substring.

    Empty query lists all indexed files. Matching is case-insensitive against
    the full ``source`` path and the basename.
    """
    settings = get_settings()
    store = VectorStore(
        persist_dir=settings.resolved_chroma_path(),
        embedding_model=settings.embedding_model,
    )
    files = store.list_indexed_files()
    query = (name_query or "").strip()
    if not query:
        matched = files
    else:
        q = query.lower()
        matched = []
        for f in files:
            source = str(f.get("source", ""))
            name = Path(source).name
            if q in source.lower() or q in name.lower():
                matched.append(f)

    payload = {
        "query": query,
        "total_indexed": len(files),
        "match_count": len(matched),
        "files": matched,
    }
    if not files:
        payload["message"] = "知识库为空：尚未导入任何文档。"
    elif not matched:
        payload["message"] = f"未找到文件名或路径包含「{query}」的已导入文档。"
    return json.dumps(payload, ensure_ascii=False)
