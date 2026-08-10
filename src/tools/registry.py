"""Tool registry: OpenAI tool schemas + dispatch."""

from __future__ import annotations

import json
from typing import Any, Callable

from src.rag.generate import build_context
from src.rag.retriever import Retriever
from src.tools.calculator import calculate
from src.tools.time_tool import get_current_time

ToolHandler = Callable[..., str]


def _retrieve_knowledge(query: str, top_k: int | None = None) -> str:
    retriever = Retriever()
    k = top_k or retriever.final_k
    hits = retriever.retrieve(query, top_k=k)
    if not hits:
        return "检索结果为空：知识库未命中相关片段。"
    # Keep machine-readable block for later citation in final answer
    payload = {
        "count": len(hits),
        "chunks": [
            {
                "n": i,
                "source": h.source,
                "heading_path": h.heading_path,
                "page": h.page,
                "score": round(h.score, 4),
                "text": h.text,
            }
            for i, h in enumerate(hits, start=1)
        ],
        "formatted": build_context(hits),
    }
    return json.dumps(payload, ensure_ascii=False)


HANDLERS: dict[str, ToolHandler] = {
    "calculator": lambda expression: calculate(expression),
    "get_current_time": lambda: get_current_time(),
    "retrieve_knowledge": lambda query, top_k=None: _retrieve_knowledge(
        query, int(top_k) if top_k is not None else None
    ),
}


def openai_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": (
                    "计算数学表达式的精确结果。当用户需要四则运算、乘除、括号运算时使用。"
                    "不要用检索知识库来做算术。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "算术表达式，例如 (35+17)*4-20",
                        }
                    },
                    "required": ["expression"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": (
                    "获取运行环境的当前本地日期、时间和星期。"
                    "当用户询问今天几号、星期几、现在几点时使用。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "retrieve_knowledge",
                "description": (
                    "从已导入的个人知识库（Markdown/PDF）检索相关笔记片段。"
                    "当问题涉及文档中的概念、参数、制度、定义时使用。"
                    "不要用此工具回答纯算术或当前时间。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "检索用查询词，尽量包含专有名词",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "返回条数，默认使用系统配置",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
    ]


def run_tool(name: str, arguments: dict[str, Any] | str | None) -> str:
    if name not in HANDLERS:
        return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
    if isinstance(arguments, str):
        raw = arguments.strip() or "{}"
        try:
            args = json.loads(raw)
        except json.JSONDecodeError:
            return json.dumps(
                {"error": f"工具参数不是合法 JSON: {arguments}"},
                ensure_ascii=False,
            )
    else:
        args = arguments or {}
    if not isinstance(args, dict):
        return json.dumps({"error": "工具参数必须是对象"}, ensure_ascii=False)
    try:
        if name == "calculator":
            return HANDLERS[name](expression=str(args.get("expression", "")))
        if name == "get_current_time":
            return HANDLERS[name]()
        if name == "retrieve_knowledge":
            return HANDLERS[name](
                query=str(args.get("query", "")),
                top_k=args.get("top_k"),
            )
        return HANDLERS[name](**args)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": str(e)}, ensure_ascii=False)
