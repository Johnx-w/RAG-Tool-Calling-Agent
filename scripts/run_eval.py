"""Run eval_questions.json against the Agent (Phase 3)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent.loop import run_agent  # noqa: E402
from src.rag.qa import ask_rag  # noqa: E402

QUESTIONS = ROOT / "tests" / "eval_questions.json"
OUT_JSON = ROOT / "tests" / "eval_run.json"
OUT_MD = ROOT / "tests" / "eval_results.md"


def _norm(s: str) -> str:
    s = re.sub(r"[*_`#\[\]()>]", "", s or "")
    return re.sub(r"\s+", "", s.lower())


def _canon_action(name: str) -> str:
    n = (name or "").strip()
    aliases = {
        "retrieve": "retrieve_knowledge",
        "retrieve_knowledge": "retrieve_knowledge",
        "search": "retrieve_knowledge",
        "calculator": "calculator",
        "calc": "calculator",
        "get_current_time": "get_current_time",
        "time": "get_current_time",
        "finish": "finish",
    }
    return aliases.get(n, n)


def _action_names(steps: list[dict]) -> list[str]:
    names = []
    for s in steps:
        if s.get("action_type") == "tool":
            names.append(_canon_action(s.get("action_name") or ""))
        elif s.get("action_name") == "finish":
            names.append("finish")
    return names


def _actions_ok(expected: list[str], actual: list[str]) -> bool:
    """Loose check: expected tools appear in order (finish optional at end)."""
    exp = [_canon_action(e) for e in expected if _canon_action(e) != "finish"]
    act = [a for a in actual if a != "finish"]
    if not exp:
        return True
    i = 0
    for a in act:
        if i < len(exp) and a == exp[i]:
            i += 1
    return i == len(exp)


def _points_hit(points: list[str], answer: str) -> float | None:
    if not points:
        return None
    ans = _norm(answer)
    # instructional points like「包含日期」→ check rough presence
    soft = {
        "包含日期": any(ch.isdigit() for ch in answer)
        and ("-" in answer or "年" in answer or "月" in answer or "日" in answer),
        "包含星期": "星期" in answer or "周" in answer,
        "小时": "时" in answer or ":" in answer,
        "分钟": "分" in answer or ":" in answer,
    }
    hit = 0
    for p in points:
        if p in soft:
            hit += 1 if soft[p] else 0
        elif _norm(p) in ans:
            hit += 1
    return hit / len(points)


def _source_hit(gold_sources: list[str], citations: list[dict], answer: str) -> bool | None:
    if not gold_sources:
        return None
    blob = _norm(answer) + _norm(json.dumps(citations, ensure_ascii=False))
    for g in gold_sources:
        name = Path(g).name
        if _norm(name) in blob or _norm(g) in blob:
            return True
    return False


def evaluate_one(q: dict, *, mode: str) -> dict:
    question = q["question"]
    if mode == "rag":
        result = ask_rag(question)
        steps = [{"action_type": "tool", "action_name": "retrieve_knowledge"}]
        if result.get("status") == "refused":
            steps.append({"action_type": "finish", "action_name": "finish"})
        else:
            steps.append({"action_type": "finish", "action_name": "finish"})
        citations = result.get("citations") or []
        # map rag citations
        retrieved_sources = [c.get("source", "") for c in citations]
    else:
        result = run_agent(question)
        steps = result.get("steps") or []
        citations = result.get("citations") or []
        retrieved_sources = [c.get("source", "") for c in citations]

    actual_actions = _action_names(steps)
    expected_actions = q.get("expected_actions") or []
    actions_ok = _actions_ok(expected_actions, actual_actions)
    expected_status = q.get("expected_status") or "answered"
    status = result.get("status") or ""
    answer = result.get("answer") or ""

    # K-max style: if answer asserts undefined, treat as refuse-equivalent
    refuse_equiv = (
        "未定义" in answer
        or "无法确定" in answer
        or "未给出" in answer
        or "并未给出" in answer
    )
    status_ok = status == expected_status or (
        expected_status == "refused" and refuse_equiv
    )
    # 对抗题：拒绝错误前提且忠实笔记，即使 status=refused 也可算答对
    if (
        expected_status == "answered"
        and status == "refused"
        and ("并未" in answer or "未断言" in answer or ("没有" in answer and "强于" in answer))
    ):
        status_ok = True

    source_ok = _source_hit(q.get("gold_sources") or [], citations, answer)
    points = _points_hit(q.get("gold_answer_points") or [], answer)

    # must_not_cite
    forbidden = q.get("must_not_cite") or q.get("must_not_cite_as_answer_source") or []
    forbidden_ok = True
    for f in forbidden:
        if _norm(Path(f).name) in _norm(answer):
            # weak check: mentioning forbidden file as answer source
            if "来源" in answer and Path(f).name in answer:
                forbidden_ok = False

    passed = bool(status_ok and actions_ok and forbidden_ok)
    if source_ok is False and (q.get("gold_sources") or []) and expected_status == "answered":
        passed = False
    if (
        points is not None
        and points < 0.34
        and expected_status == "answered"
        and status == "answered"
    ):
        passed = False

    return {
        "id": q["id"],
        "category": q.get("category"),
        "question": question,
        "mode": mode,
        "expected_actions": expected_actions,
        "actual_actions": actual_actions,
        "actions_ok": actions_ok,
        "expected_status": expected_status,
        "status": status,
        "status_ok": status_ok,
        "source_ok": source_ok,
        "points_hit_ratio": points,
        "forbidden_ok": forbidden_ok,
        "passed": passed,
        "trace_id": result.get("trace_id"),
        "answer_preview": answer[:240].replace("\n", " "),
        "retrieved_sources": retrieved_sources,
    }


def write_markdown(rows: list[dict], summary: dict) -> None:
    lines = [
        "# 评估结果",
        "",
        f"> 生成时间（UTC）：{summary['finished_at']}",
        f"> 模式：{summary['mode']}；hybrid 以当前 `configs/default.yaml` 为准",
        "",
        "## 汇总",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 总题数 | {summary['total']} |",
        f"| 通过数 | {summary['passed']} |",
        f"| 通过率 | {summary['pass_rate']} |",
        f"| 动作序列正确率 | {summary['actions_rate']} |",
        f"| 状态（含拒答等价）正确率 | {summary['status_rate']} |",
        "",
        "## 分题记录",
        "",
        "| id | 类别 | 动作符合 | 状态符合 | 来源命中 | 要点命中 | 通过 | 备注 |",
        "|----|------|----------|----------|----------|----------|------|------|",
    ]
    for r in rows:
        notes = []
        if not r["actions_ok"]:
            notes.append(f"期望{r['expected_actions']}实得{r['actual_actions']}")
        if not r["status_ok"]:
            notes.append(f"期望状态{r['expected_status']}实得{r['status']}")
        if r["source_ok"] is False:
            notes.append("未命中金标来源")
        if r.get("points_hit_ratio") is not None and r["points_hit_ratio"] < 0.34:
            notes.append(f"要点命中{r['points_hit_ratio']:.2f}")
        note = "; ".join(notes) or r.get("answer_preview", "")[:60]
        lines.append(
            f"| {r['id']} | {r['category']} | {r['actions_ok']} | {r['status_ok']} | "
            f"{r['source_ok']} | {r['points_hit_ratio']} | {r['passed']} | {note} |"
        )

    # failure cases: first 3 failed, or lowest quality
    fails = [r for r in rows if not r["passed"]][:5]
    lines += ["", "## 失败 Case 分析（至少 3 条）", ""]
    if not fails:
        lines.append("本次全部通过或近似通过；下列选取边界题作说明。")
        fails = rows[:3]
    for i, r in enumerate(fails[:3], start=1):
        root = "决策" if not r["actions_ok"] else (
            "生成/拒答" if not r["status_ok"] else "检索/忠实度"
        )
        lines += [
            f"### Case {i}: {r['id']}",
            "",
            f"- 题号：`{r['id']}`",
            f"- 现象：{r.get('answer_preview','')}",
            f"- 根因归类：**{root}**（动作符合={r['actions_ok']}，状态符合={r['status_ok']}，来源命中={r['source_ok']}）",
            f"- 改进：对照期望动作 `{r['expected_actions']}` 与 Trace `{r.get('trace_id')}`；"
            f"必要时收紧 Prompt、增强 BM25 专有词、或补充拒答模板。",
            "",
        ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["agent", "rag"], default="agent")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 题，0=全部")
    parser.add_argument("--ids", type=str, default="", help="逗号分隔题号，如 T01,H01")
    args = parser.parse_args()

    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    questions = data["questions"]
    if args.ids:
        want = {x.strip() for x in args.ids.split(",") if x.strip()}
        questions = [q for q in questions if q["id"] in want]
    if args.limit and args.limit > 0:
        questions = questions[: args.limit]

    rows = []
    for i, q in enumerate(questions, start=1):
        print(f"[{i}/{len(questions)}] {q['id']} ...", flush=True)
        try:
            row = evaluate_one(q, mode=args.mode)
        except Exception as e:  # noqa: BLE001
            row = {
                "id": q["id"],
                "category": q.get("category"),
                "question": q["question"],
                "mode": args.mode,
                "expected_actions": q.get("expected_actions"),
                "actual_actions": [],
                "actions_ok": False,
                "expected_status": q.get("expected_status"),
                "status": "error",
                "status_ok": False,
                "source_ok": None,
                "points_hit_ratio": None,
                "forbidden_ok": False,
                "passed": False,
                "trace_id": None,
                "answer_preview": f"ERROR: {e}",
                "retrieved_sources": [],
            }
        rows.append(row)
        print(
            f"  -> passed={row['passed']} actions={row['actual_actions']} status={row['status']}",
            flush=True,
        )

    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    actions_ok = sum(1 for r in rows if r["actions_ok"])
    status_ok = sum(1 for r in rows if r["status_ok"])
    summary = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "total": total,
        "passed": passed,
        "pass_rate": f"{(passed / total * 100) if total else 0:.1f}%",
        "actions_rate": f"{(actions_ok / total * 100) if total else 0:.1f}%",
        "status_rate": f"{(status_ok / total * 100) if total else 0:.1f}%",
    }
    OUT_JSON.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
