"""CLI: ingest + Phase1 RAG ask + Phase2 Agent ask + show-trace."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from src.agent.loop import run_agent
from src.agent.trace import list_recent_traces, load_trace
from src.config import ROOT
from src.ingest.pipeline import ingest_directory, ingest_paths
from src.rag.qa import ask_rag

app = typer.Typer(
    add_completion=False,
    help="RAG + Tool Calling Agent (Phase 2: Agent + tools)",
)


@app.command("ingest-sample")
def ingest_sample_cmd() -> None:
    """Ingest data/sample into Chroma."""
    report = ingest_directory()
    typer.echo(
        f"files={len(report.files)} docs={report.documents} chunks={report.chunks}"
    )
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
    typer.echo(
        f"files={len(report.files)} docs={report.documents} chunks={report.chunks}"
    )
    for e in report.errors:
        typer.echo(f"  ERR {e}")
    if report.errors and not report.files:
        raise typer.Exit(code=1)


@app.command("ask")
def ask_cmd(
    question: str = typer.Argument(..., help="User question"),
    rag_only: bool = typer.Option(
        False,
        "--rag-only",
        help="Use Phase 1 fixed retrieve→generate pipeline (no tools)",
    ),
    show_steps: bool = typer.Option(
        False, "--show-steps", help="Print agent tool steps"
    ),
    show_retrieve: bool = typer.Option(
        False, "--show-retrieve", help="(rag-only) Print retrieved chunks"
    ),
) -> None:
    """Default: Agent decides retrieve/tools. Use --rag-only for Phase 1 pipeline."""
    if rag_only:
        result = ask_rag(question)
        if show_retrieve:
            typer.echo("--- retrieved ---")
            typer.echo(json.dumps(result["retrieved"], ensure_ascii=False, indent=2))
            typer.echo("--- answer ---")
        typer.echo(result["answer"])
        typer.echo(f"\n[status={result['status']} mode=rag-only]")
        return

    result = run_agent(question)
    if show_steps:
        typer.echo("--- steps ---")
        typer.echo(json.dumps(result["steps"], ensure_ascii=False, indent=2))
        typer.echo("--- answer ---")
    typer.echo(result["answer"])
    typer.echo(
        f"\n[status={result['status']} mode=agent trace_id={result['trace_id']}]"
    )


@app.command("show-trace")
def show_trace_cmd(
    trace_id: str = typer.Argument(
        "",
        help="Trace id (prefix ok). Empty = list recent.",
    ),
    limit: int = typer.Option(10, help="How many recent traces to list"),
) -> None:
    if not trace_id:
        rows = list_recent_traces(limit=limit)
        if not rows:
            typer.echo("暂无 trace。先运行: python -m src.main ask \"...\"")
            return
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    data = load_trace(trace_id)
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
