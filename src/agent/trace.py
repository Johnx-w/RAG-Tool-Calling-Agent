"""Agent run trace persistence."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import ROOT, get_config


@dataclass
class TraceStep:
    step_index: int
    reasoning_summary: str
    action_type: str  # tool | finish
    action_name: str
    action_input: dict[str, Any] | str | None
    observation_summary: str
    retrieved_refs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TraceRecord:
    trace_id: str
    question: str
    started_at: str
    finished_at: str = ""
    steps: list[TraceStep] = field(default_factory=list)
    final_answer: str = ""
    status: str = "answered"  # answered | refused | error
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "question": self.question,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "steps": [asdict(s) for s in self.steps],
            "final": {
                "answer": self.final_answer,
                "status": self.status,
                "error": self.error or None,
            },
        }


def _trace_dir() -> Path:
    cfg = get_config().get("trace", {})
    rel = cfg.get("dir", "traces")
    path = Path(rel)
    if not path.is_absolute():
        path = ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_trace(question: str) -> TraceRecord:
    return TraceRecord(
        trace_id=uuid.uuid4().hex[:12],
        question=question,
        started_at=datetime.now(timezone.utc).isoformat(),
    )


def summarize_observation(text: str, limit: int = 240) -> str:
    t = (text or "").replace("\n", " ").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 3] + "..."


def save_trace(trace: TraceRecord) -> Path | None:
    cfg = get_config().get("trace", {})
    if not cfg.get("save_jsonl", True):
        return None
    trace.finished_at = datetime.now(timezone.utc).isoformat()
    path = _trace_dir() / f"{trace.trace_id}.json"
    path.write_text(
        json.dumps(trace.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # also append index line
    index = _trace_dir() / "index.jsonl"
    with index.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "trace_id": trace.trace_id,
                    "question": trace.question,
                    "status": trace.status,
                    "finished_at": trace.finished_at,
                    "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    return path


def load_trace(trace_id: str) -> dict[str, Any]:
    path = _trace_dir() / f"{trace_id}.json"
    if not path.exists():
        # allow prefix match
        matches = sorted(_trace_dir().glob(f"{trace_id}*.json"))
        if not matches:
            raise FileNotFoundError(f"未找到 trace: {trace_id}")
        path = matches[-1]
    return json.loads(path.read_text(encoding="utf-8"))


def list_recent_traces(limit: int = 10) -> list[dict[str, Any]]:
    index = _trace_dir() / "index.jsonl"
    if not index.exists():
        return []
    lines = index.read_text(encoding="utf-8").strip().splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    return rows[-limit:]
