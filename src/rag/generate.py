"""Context assembly + grounded generation with citations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from openai import OpenAI

from src.config import Settings, get_config, get_settings
from src.rag.models import RetrievedChunk

_CITE_RE = re.compile(r"\[(\d+)\]")


SYSTEM_PROMPT = """你是个人知识库问答助手（Phase 1：固定检索流水线）。
只根据「检索到的笔记」回答；禁止用外部常识补全笔记中没有的结论、数字或定义。

引用规则：
- 每条关键结论后标注来源编号，如 [1]、[2]
- 编号必须对应下方笔记块；不得编造不存在的编号或页码

若笔记不足以回答：
- 只输出：根据现有笔记无法确定。
- 并可列出已检索到的文件名范围
- 不要猜测、不要扩写
"""


@dataclass
class GenerationResult:
    answer: str
    status: str  # answered | refused
    citations: list[dict]
    contexts: list[RetrievedChunk]


def build_context(hits: list[RetrievedChunk], max_chars: int = 12000) -> str:
    blocks: list[str] = []
    used = 0
    for i, h in enumerate(hits, start=1):
        block = f"{h.header(i)}\n{h.text}\n"
        if used + len(block) > max_chars:
            break
        blocks.append(block)
        used += len(block)
    return "\n".join(blocks)


def validate_citations(answer: str, n_contexts: int) -> list[int]:
    nums = [int(x) for x in _CITE_RE.findall(answer)]
    return [n for n in nums if 1 <= n <= n_contexts]


def _is_refuse(answer: str, refuse_text: str) -> bool:
    a = answer.strip()
    return refuse_text in a or a.startswith("根据现有笔记无法确定")


class Generator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.llm_api_key:
            raise RuntimeError("缺少 LLM_API_KEY：请在 .env 中配置")
        kwargs: dict = {"api_key": self.settings.llm_api_key}
        if self.settings.llm_base_url:
            kwargs["base_url"] = self.settings.llm_base_url
        self.client = OpenAI(**kwargs)
        self.model = self.settings.llm_model
        gen = get_config().get("generation", {})
        self.refuse_text = gen.get("refuse_text", "根据现有笔记无法确定。")
        # rough char budget from token-ish config
        self.max_context_chars = int(gen.get("max_context_tokens", 4000)) * 2

    def generate(self, question: str, hits: list[RetrievedChunk]) -> GenerationResult:
        if not hits:
            answer = (
                f"{self.refuse_text}\n"
                "已检索范围：知识库为空或未命中任何片段。"
            )
            return GenerationResult(
                answer=answer, status="refused", citations=[], contexts=[]
            )

        context = build_context(hits, max_chars=self.max_context_chars)
        user = (
            f"检索到的笔记：\n{context}\n\n"
            f"用户问题：{question}\n\n"
            "请作答。"
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        answer = (resp.choices[0].message.content or "").strip()
        valid_nums = validate_citations(answer, len(hits))
        citations = []
        for n in sorted(set(valid_nums)):
            h = hits[n - 1]
            citations.append(
                {
                    "n": n,
                    "source": h.source,
                    "heading_path": h.heading_path,
                    "page": h.page,
                    "score": round(h.score, 4),
                }
            )

        status = "refused" if _is_refuse(answer, self.refuse_text) else "answered"
        # append footnote for UX if answered and has cites
        if status == "answered" and citations:
            foot = ["", "来源："]
            for c in citations:
                page = f", page={c['page']}" if c["page"] else ""
                foot.append(
                    f"[{c['n']}] {c['source']} | {c['heading_path'] or '-'}{page}"
                )
            if "来源：" not in answer:
                answer = answer + "\n" + "\n".join(foot)

        return GenerationResult(
            answer=answer, status=status, citations=citations, contexts=hits
        )
