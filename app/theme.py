"""Shared Streamlit theme: soft mint + white."""

from __future__ import annotations

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,650&family=Figtree:wght@400;500;600;700&display=swap');

:root {
  --bg: #f3f8f5;
  --bg-deep: #e7f2eb;
  --surface: #ffffff;
  --ink: #15261d;
  --muted: #5a7264;
  --accent: #2f7a5b;
  --accent-soft: #d5ebe0;
  --line: #c9ddd2;
  --warn: #8a5a2b;
  --refuse: #7a4a4a;
}

html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
  color: var(--ink);
  font-family: "Figtree", "Segoe UI", sans-serif;
}

[data-testid="stHeader"] {
  background: transparent !important;
}

/* 兜底隐藏 Streamlit 自带 Deploy（云端部署）按钮 */
.stAppDeployButton,
[data-testid="stAppDeployButton"] {
  display: none !important;
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #eef7f1 0%, #f7fbf8 100%) !important;
  border-right: 1px solid var(--line);
}

[data-testid="stSidebar"] * {
  font-family: "Figtree", "Segoe UI", sans-serif !important;
}

.block-container {
  padding-top: 1.6rem !important;
  padding-bottom: 3rem !important;
  max-width: 920px !important;
}

h1, h2, h3, .brand-title {
  font-family: "Fraunces", Georgia, serif !important;
  color: var(--ink) !important;
  letter-spacing: -0.02em;
  font-weight: 650 !important;
}

.hero {
  background:
    radial-gradient(1200px 280px at 10% -20%, #d9eee3 0%, transparent 55%),
    linear-gradient(180deg, #ffffff 0%, #f7fbf8 100%);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 1.35rem 1.5rem 1.2rem;
  margin-bottom: 1.25rem;
}

.brand-title {
  font-size: 1.85rem;
  margin: 0 0 0.35rem 0;
  line-height: 1.15;
}

.brand-sub {
  margin: 0;
  color: var(--muted);
  font-size: 0.98rem;
  line-height: 1.55;
  max-width: 42rem;
}

.capability-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem 0.9rem;
  margin-top: 0.9rem;
  color: var(--accent);
  font-size: 0.86rem;
  font-weight: 600;
}

.capability-row span::before {
  content: "";
  display: inline-block;
  width: 0.45rem;
  height: 0.45rem;
  margin-right: 0.4rem;
  border-radius: 50%;
  background: var(--accent);
  vertical-align: 0.1rem;
}

.panel {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 1rem 1.15rem;
  margin: 0.75rem 0 1rem;
}

.panel-title {
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.05rem;
  font-weight: 650;
  margin: 0 0 0.65rem 0;
  color: var(--ink);
}

.meta-line {
  color: var(--muted);
  font-size: 0.86rem;
  margin-top: 0.55rem;
}

.status-pill {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  background: var(--accent-soft);
  color: var(--accent);
}

.status-pill.refused {
  background: #f3e4e4;
  color: var(--refuse);
}

.step {
  border-left: 3px solid var(--accent-soft);
  padding: 0.55rem 0 0.55rem 0.9rem;
  margin: 0.35rem 0;
}

.step-head {
  font-weight: 650;
  color: var(--ink);
  font-size: 0.92rem;
}

.step-body {
  color: var(--muted);
  font-size: 0.86rem;
  margin-top: 0.2rem;
  line-height: 1.45;
  word-break: break-word;
}

.answer-box {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 1rem 1.1rem;
  white-space: pre-wrap;
  line-height: 1.6;
  font-size: 0.98rem;
}

div[data-testid="stButton"] > button {
  background: var(--accent) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
}

div[data-testid="stButton"] > button:hover {
  background: #25664b !important;
  color: #fff !important;
}

div[data-baseweb="select"] > div,
.stTextInput input,
.stTextArea textarea {
  border-radius: 10px !important;
}

[data-testid="stFileUploader"] {
  background: var(--surface);
  border: 1px dashed var(--line);
  border-radius: 14px;
  padding: 0.4rem;
}

hr {
  border: none;
  border-top: 1px solid var(--line);
  margin: 1.2rem 0;
}
</style>
"""


def inject_theme() -> None:
    import streamlit as st

    st.markdown(THEME_CSS, unsafe_allow_html=True)


def render_hero(subtitle: str) -> None:
    import streamlit as st

    st.markdown(
        f"""
<div class="hero">
  <div class="brand-title">RAG Agent</div>
  <p class="brand-sub">{subtitle}</p>
  <div class="capability-row">
    <span>混合检索</span>
    <span>工具调用</span>
    <span>引用 / 拒答</span>
    <span>逐步 Trace</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
