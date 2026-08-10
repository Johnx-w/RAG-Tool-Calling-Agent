"""One-click ingest for sample corpus."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingest.pipeline import ingest_directory  # noqa: E402


def main() -> None:
    report = ingest_directory()
    print(f"files={len(report.files)} docs={report.documents} chunks={report.chunks}")
    for f in report.files:
        print(f"  + {f}")
    for e in report.errors:
        print(f"  ERR {e}")
    if report.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
