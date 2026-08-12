"""Streamlit UI for RAG + Tool Calling Agent."""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.theme import inject_theme, render_hero
from src.agent.loop import run_agent
from src.agent.trace import list_recent_traces, load_trace
from src.config import get_config, get_settings
from src.ingest.pipeline import ingest_directory, ingest_paths
from src.rag.qa import ask_rag
from src.rag.vectorstore import VectorStore
from src.tools.file_query import find_indexed_file

EXAMPLE_QUESTIONS = [
    "根据优化器学习笔记，Adam 同时维护了哪些矩估计？",
    "(35+17)*4-20 等于多少？",
    "知识库里有没有文件名包含 alphacore 的已导入文档？",
    "查阅 AlphaCore-7 的额定功耗（单位 W），再计算它的 3 倍是多少。",
    "我笔记里把私人缩写 K-max 定义成什么？",
]


def _esc(text: object) -> str:
    return html.escape(str(text or ""), quote=True)


def _fmt_json(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _render_steps(steps: list[dict]) -> None:
    if not steps:
        st.caption("本轮无工具步骤（模型直接作答）。")
        return
    for s in steps:
        name = s.get("action_name") or "-"
        kind = s.get("action_type") or ""
        idx = s.get("step_index", "")
        obs = s.get("observation_summary") or ""
        inp = s.get("action_input")
        inp_s = ""
        if inp not in (None, "", {}):
            inp_s = _fmt_json(inp) if isinstance(inp, (dict, list)) else str(inp)
        st.markdown(
            f"""
<div class="step">
  <div class="step-head">步骤 {_esc(idx)} · {_esc(name)} <span style="color:#5a7264;font-weight:500">({_esc(kind)})</span></div>
  <div class="step-body">{_esc(obs)}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if inp_s:
            with st.expander(f"输入参数 · {name}", expanded=False):
                st.code(inp_s, language="json")


def page_chat() -> None:
    inject_theme()
    render_hero(
        "个人知识库 Agent：按问题决定检索或调用工具，回答带来源引用；证据不足则拒答，全程可回放 Trace。"
    )

    with st.sidebar:
        st.markdown("### 对话设置")
        mode = st.radio(
            "模式",
            options=["agent", "rag-only"],
            format_func=lambda x: "Agent（工具决策）" if x == "agent" else "RAG-only（固定检索）",
            index=0,
        )
        show_steps = st.checkbox("显示工具步骤", value=True)
        st.markdown("### 示例问题")
        for i, q in enumerate(EXAMPLE_QUESTIONS):
            if st.button(q, key=f"ex_{i}", use_container_width=True):
                st.session_state["draft_question"] = q

    draft = st.session_state.get("draft_question", "")
    question = st.text_area(
        "输入问题",
        value=draft,
        height=110,
        placeholder="例如：AlphaCore-7 额定功耗的 3 倍是多少？",
    )
    col_a, col_b = st.columns([1, 3])
    with col_a:
        ask = st.button("发送", type="primary", use_container_width=True)

    if ask:
        q = (question or "").strip()
        if not q:
            st.warning("请先输入问题。")
            return
        st.session_state["draft_question"] = q
        with st.spinner("思考与调用工具中…"):
            try:
                if mode == "rag-only":
                    result = ask_rag(q)
                    steps: list[dict] = []
                    trace_id = ""
                    status = result.get("status", "answered")
                    answer = result.get("answer", "")
                else:
                    result = run_agent(q)
                    steps = result.get("steps") or []
                    trace_id = result.get("trace_id") or ""
                    status = result.get("status", "answered")
                    answer = result.get("answer", "")
            except Exception as e:  # noqa: BLE001
                st.error(f"调用失败：{e}")
                return

        st.session_state["last_result"] = {
            "question": q,
            "answer": answer,
            "status": status,
            "steps": steps,
            "trace_id": trace_id,
            "mode": mode,
        }

    last = st.session_state.get("last_result")
    if not last:
        st.markdown(
            '<div class="panel"><div class="panel-title">开始提问</div>'
            "<div class=\"step-body\">左侧可选示例；Agent 模式会展示检索 / 计算器 / 时间 / 文件查询等工具轨迹。</div></div>",
            unsafe_allow_html=True,
        )
        return

    status = last["status"]
    pill_cls = "status-pill refused" if status == "refused" else "status-pill"
    st.markdown(
        f'<div class="panel"><div class="panel-title">回答 '
        f'<span class="{pill_cls}">{_esc(status)}</span></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="answer-box">{_esc(last["answer"])}</div>',
        unsafe_allow_html=True,
    )

    meta = f"模式 · {_esc(last['mode'])}"
    if last.get("trace_id"):
        meta += f"  ·  Trace · {_esc(last['trace_id'])}"
    st.markdown(f'<div class="meta-line">{meta}</div>', unsafe_allow_html=True)

    if show_steps and last["mode"] == "agent":
        st.markdown("---")
        st.markdown('<div class="panel-title">工具调用轨迹</div>', unsafe_allow_html=True)
        _render_steps(last.get("steps") or [])


def page_knowledge() -> None:
    inject_theme()
    render_hero("导入 Markdown / PDF，写入向量库与 BM25；也可按文件名查询已索引文档。")

    uploads_dir = ROOT / (get_config().get("ingest", {}) or {}).get(
        "uploads_dir", "data/uploads"
    )
    uploads_dir.mkdir(parents=True, exist_ok=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("摄入样例语料", use_container_width=True):
            with st.spinner("正在 ingest-sample…"):
                try:
                    report = ingest_directory()
                    st.success(
                        f"完成：files={len(report.files)} docs={report.documents} "
                        f"chunks={report.chunks}"
                    )
                    if report.errors:
                        st.warning("\n".join(report.errors))
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))
    with c2:
        st.caption(f"上传目录：`{uploads_dir.relative_to(ROOT).as_posix()}`")

    uploaded = st.file_uploader(
        "上传 MD / PDF",
        type=["md", "pdf"],
        accept_multiple_files=True,
    )
    if uploaded and st.button("导入所选文件", type="primary"):
        paths: list[Path] = []
        for f in uploaded:
            dest = uploads_dir / f.name
            dest.write_bytes(f.getvalue())
            paths.append(dest)
        with st.spinner("切分 · Embedding · 入库…"):
            try:
                report = ingest_paths(paths)
                st.success(
                    f"导入完成：files={len(report.files)} chunks={report.chunks}"
                )
                for err in report.errors:
                    st.error(err)
            except Exception as e:  # noqa: BLE001
                st.error(str(e))

    st.markdown("---")
    st.markdown('<div class="panel-title">已索引文档</div>', unsafe_allow_html=True)
    q = st.text_input("按文件名筛选（可空=全部）", value="")
    try:
        raw = find_indexed_file(q.strip())
        data = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        st.error(f"读取索引失败：{e}")
        return

    files = data.get("files") or []
    st.caption(
        f"匹配 {data.get('match_count', 0)} / 已索引 {data.get('total_indexed', 0)}"
    )
    if not files:
        st.info(data.get("message") or "暂无文档。可先摄入样例语料。")
        return

    for item in files:
        st.markdown(
            f"""
<div class="panel">
  <div class="step-head">{_esc(item.get("source", ""))}</div>
  <div class="step-body">type={_esc(item.get("file_type") or "-")} · chunks={_esc(item.get("chunk_count"))} · doc_id={_esc(item.get("doc_id"))}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    settings = get_settings()
    store = VectorStore(
        persist_dir=settings.resolved_chroma_path(),
        embedding_model=settings.embedding_model,
    )
    st.markdown(
        f'<div class="meta-line">Chroma 块数 · {store.count()}</div>',
        unsafe_allow_html=True,
    )


def page_traces() -> None:
    inject_theme()
    render_hero("回放每一次 Agent 决策：reasoning 摘要、工具输入与 observation、最终状态。")

    rows = list_recent_traces(limit=20)
    if not rows:
        st.info("暂无 Trace。请先在「对话」页用 Agent 模式提问。")
        return

    labels = [
        f"{r.get('trace_id')} · {r.get('status')} · {(r.get('question') or '')[:36]}"
        for r in reversed(rows)
    ]
    choice = st.selectbox("选择 Trace", options=labels)
    tid = choice.split(" · ", 1)[0].strip()
    try:
        data = load_trace(tid)
    except Exception as e:  # noqa: BLE001
        st.error(str(e))
        return

    final = data.get("final") or {}
    status = final.get("status") or data.get("status") or ""
    pill_cls = "status-pill refused" if status == "refused" else "status-pill"
    st.markdown(
        f"""
<div class="panel">
  <div class="panel-title">问题</div>
  <div class="step-body">{_esc(data.get("question", ""))}</div>
  <div class="meta-line">trace_id · {_esc(data.get("trace_id"))} · <span class="{pill_cls}">{_esc(status)}</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="panel-title">步骤</div>', unsafe_allow_html=True)
    _render_steps(data.get("steps") or [])

    st.markdown('<div class="panel-title">最终回答</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="answer-box">{_esc(final.get("answer") or "")}</div>',
        unsafe_allow_html=True,
    )

    with st.expander("原始 JSON", expanded=False):
        st.code(_fmt_json(data), language="json")


def main() -> None:
    st.set_page_config(
        page_title="RAG Agent",
        page_icon=":herb:",
        layout="centered",
        initial_sidebar_state="expanded",
    )
    chat = st.Page(page_chat, title="对话", default=True)
    knowledge = st.Page(page_knowledge, title="知识库")
    traces = st.Page(page_traces, title="Trace")
    nav = st.navigation([chat, knowledge, traces])
    nav.run()


if __name__ == "__main__":
    main()
