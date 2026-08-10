"""Tool-calling agent loop."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from src.agent.prompts import AGENT_SYSTEM_PROMPT
from src.agent.trace import (
    TraceStep,
    new_trace,
    save_trace,
    summarize_observation,
)
from src.config import get_config, get_settings
from src.tools.registry import openai_tool_schemas, run_tool

_REFUSE_RE = re.compile(r"根据现有笔记无法确定")


def _extract_retrieve_refs(observation: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(observation)
    except json.JSONDecodeError:
        return []
    chunks = data.get("chunks") or []
    refs = []
    for c in chunks:
        refs.append(
            {
                "n": c.get("n"),
                "source": c.get("source"),
                "heading_path": c.get("heading_path"),
                "page": c.get("page"),
                "score": c.get("score"),
            }
        )
    return refs


def _append_citation_footer(answer: str, refs: list[dict[str, Any]]) -> str:
    if not refs or "来源：" in answer:
        return answer
    # only include refs whose [n] appears, else all retrieved
    used = {int(x) for x in re.findall(r"\[(\d+)\]", answer)}
    chosen = [r for r in refs if r.get("n") in used] if used else refs
    if not chosen:
        return answer
    lines = ["", "来源："]
    for r in chosen:
        page = f", page={r['page']}" if r.get("page") else ""
        lines.append(
            f"[{r['n']}] {r.get('source','')} | {r.get('heading_path') or '-'}{page}"
        )
    return answer + "\n" + "\n".join(lines)


def run_agent(question: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("缺少 LLM_API_KEY")
    cfg = get_config().get("agent", {})
    max_steps = int(cfg.get("max_steps", 6))

    kwargs: dict[str, Any] = {"api_key": settings.llm_api_key}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    client = OpenAI(**kwargs)

    tools = openai_tool_schemas()
    if not cfg.get("retrieve_as_tool", True):
        tools = [t for t in tools if t["function"]["name"] != "retrieve_knowledge"]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    trace = new_trace(question)
    all_refs: list[dict[str, Any]] = []
    final_answer = ""
    status = "answered"

    try:
        for step in range(1, max_steps + 1):
            resp = client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
            )
            msg = resp.choices[0].message
            tool_calls = msg.tool_calls or []

            if not tool_calls:
                final_answer = (msg.content or "").strip()
                reasoning = "模型给出最终回答（未再请求工具）"
                if _REFUSE_RE.search(final_answer):
                    status = "refused"
                final_answer = _append_citation_footer(final_answer, all_refs)
                trace.steps.append(
                    TraceStep(
                        step_index=step,
                        reasoning_summary=reasoning,
                        action_type="finish",
                        action_name="finish",
                        action_input=None,
                        observation_summary=summarize_observation(final_answer),
                        retrieved_refs=list(all_refs),
                    )
                )
                break

            # assistant message with tool calls must be recorded
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tc in tool_calls:
                name = tc.function.name
                raw_args = tc.function.arguments or "{}"
                try:
                    parsed_args: dict[str, Any] | str = json.loads(raw_args)
                except json.JSONDecodeError:
                    parsed_args = raw_args

                observation = run_tool(name, parsed_args)
                refs = []
                if name == "retrieve_knowledge":
                    refs = _extract_retrieve_refs(observation)
                    if refs:
                        all_refs = refs  # latest retrieve wins for footer

                trace.steps.append(
                    TraceStep(
                        step_index=step,
                        reasoning_summary=f"调用工具 {name}",
                        action_type="tool",
                        action_name=name,
                        action_input=parsed_args,
                        observation_summary=summarize_observation(observation),
                        retrieved_refs=refs,
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": observation,
                    }
                )
        else:
            # max steps exhausted
            status = "refused"
            final_answer = (
                "根据现有笔记无法确定。\n"
                f"（已达最大步数 {max_steps}，请缩小问题或检查知识库。）"
            )
            trace.steps.append(
                TraceStep(
                    step_index=max_steps + 1,
                    reasoning_summary="超过最大步数，强制结束",
                    action_type="finish",
                    action_name="finish",
                    action_input=None,
                    observation_summary=final_answer,
                )
            )
    except Exception as e:  # noqa: BLE001
        status = "error"
        final_answer = f"Agent 执行失败: {e}"
        trace.error = str(e)

    trace.final_answer = final_answer
    trace.status = status
    path = save_trace(trace)
    return {
        "question": question,
        "answer": final_answer,
        "status": status,
        "trace_id": trace.trace_id,
        "trace_path": str(path) if path else None,
        "steps": [
            {
                "step_index": s.step_index,
                "action_type": s.action_type,
                "action_name": s.action_name,
                "action_input": s.action_input,
                "observation_summary": s.observation_summary,
            }
            for s in trace.steps
        ],
        "citations": all_refs,
    }
