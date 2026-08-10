"""CLI entry for Phase 1: ingest + ask (RAG only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from src.config import ROOT
from src.ingest.pipeline import ingest_directory, ingest_paths
from src.rag.qa import ask_rag

app = typer.Typer(add_completion=False, help="RAG + Tool Calling Agent (Phase 1: RAG)")


@app.command("ingest-sample")
def ingest_sample_cmd() -> None:
    """Ingest data/sample into Chroma."""
    report = ingest_directory()
    typer.echo(f"files={len(report.files)} docs={report.documents} chunks={report.chunks}")
    for f in report.files:
        typer.echo(f"  + {f}")
    for s in report.skipped:
        typer.echo(f"  skip {s}")
    for e in report.errors:
        typer.echo(f"  ERR {e}")
    if report.errors:
        raise typer.Exit(code=1)


@app.command("ingest")
def ingest_cmd(
    path: Path = typer.Argument(..., help="File or directory to ingest"),
) -> None:
    path = path if path.is_absolute() else ROOT / path
    if path.is_dir():
        report = ingest_directory(path)
    else:
        report = ingest_paths([path])
    typer.echo(f"files={len(report.files)} docs={report.documents} chunks={report.chunks}")
    for e in report.errors:
        typer.echo(f"  ERR {e}")
    if report.errors and not report.files:
        raise typer.Exit(code=1)


@app.command("ask")
def ask_cmd(
    question: str = typer.Argument(..., help="Question to answer from knowledge base"),
    show_retrieve: bool = typer.Option(False, "--show-retrieve", help="Print retrieved chunks"),
) -> None:
    """Phase 1 fixed RAG pipeline (always retrieve then generate)."""
    result = ask_rag(question)
    if show_retrieve:
        typer.echo("--- retrieved ---")
        typer.echo(json.dumps(result["retrieved"], ensure_ascii=False, indent=2))
        typer.echo("--- answer ---")
    typer.echo(result["answer"])
    typer.echo(f"\n[status={result['status']}]")


if __name__ == "__main__":
    app()
