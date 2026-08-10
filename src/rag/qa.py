"""Phase 1 QA: fixed retrieve → generate pipeline."""

from __future__ import annotations

from src.rag.generate import Generator
from src.rag.retriever import Retriever


def ask_rag(question: str) -> dict:
    retriever = Retriever()
    hits = retriever.retrieve(question)
    result = Generator().generate(question, hits)
    return {
        "question": question,
        "answer": result.answer,
        "status": result.status,
        "citations": result.citations,
        "retrieved": [
            {
                "source": h.source,
                "heading_path": h.heading_path,
                "page": h.page,
                "score": round(h.score, 4),
                "preview": h.text[:120].replace("\n", " "),
            }
            for h in result.contexts
        ],
    }
