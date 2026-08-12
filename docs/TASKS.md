# 仓库目录级任务清单

状态图例：`[ ]` 未做 · `[~]` 进行中 · `[x]` 完成  

技术栈见 [TECH_STACK.md](./TECH_STACK.md)。样例语料与测试题已预置，实现时不得无故改题意；改语料必须同步改题。

---

## 目录总览

```text
RAG + Tool Calling Agent/
├── .env.example
├── requirements.txt
├── README.md                 # 含 Prompt 设计说明
├── docs/
│   ├── TECH_STACK.md
│   └── TASKS.md              # 本文件
├── configs/
│   └── default.yaml          # chunk/top_k/阈值等
├── data/
│   ├── sample/               # 冻结语料（评估用）
│   └── uploads/              # 运行时上传
├── indexes/chroma/           # 向量持久化（gitignore）
├── traces/                   # 运行 trace JSONL（gitignore）
├── scripts/
│   ├── ingest_sample.py
│   └── run_eval.py
├── src/
│   ├── __init__.py
│   ├── main.py               # CLI 入口
│   ├── config.py
│   ├── ingest/
│   ├── rag/
│   ├── tools/
│   └── agent/
└── tests/
    ├── eval_questions.json   # ≥20 题面（已写满）
    └── eval_results.md       # 跑完后填
```

---

## 0. 仓库骨架与配置 — `./` `configs/` `docs/`

| 状态 | 任务 | 路径 |
|------|------|------|
| [x] | 冻结技术栈文档 | `docs/TECH_STACK.md` |
| [x] | 目录级任务清单 | `docs/TASKS.md` |
| [x] | 写满 ≥20 道评估题 | `tests/eval_questions.json` |
| [x] | 预置样例语料（题面金标） | `data/sample/**` |
| [x] | `requirements.txt` 按 TECH_STACK 列出依赖 | `requirements.txt` |
| [x] | `.env.example` + `.gitignore`（`.env`、`indexes/`、`traces/`） | 根目录 |
| [x] | `configs/default.yaml`：`chunk_size`/`overlap`/`recall_k=20`/`final_k=5` | `configs/default.yaml` |
| [x] | 根 `README.md`：用法 + **Prompt 设计说明** | `README.md` |

---

## 1. 样例语料与导入 — `data/` `src/ingest/` `scripts/ingest_sample.py`

| 状态 | 任务 | 路径 |
|------|------|------|
| [x] | MD 语料：优化器笔记 | `data/sample/ml_optimizers.md` |
| [x] | MD 语料：AlphaCore-7 摘要（兼 PDF 同源文本） | `data/sample/alphacore7_overview.md` |
| [x] | 由同源 Markdown **导出/生成 PDF**（文本层），供 PDF 导入验收 | `data/sample/alphacore7_overview.pdf` |
| [x] | 加载 Markdown（保留标题路径元数据） | `src/ingest/loaders.py` |
| [x] | 加载 PDF（按页抽文本 + `page` 元数据；空文本报错） | `src/ingest/loaders.py` |
| [x] | 导入流水线：load → chunk → embed → upsert；支持按 `content_hash` 覆盖 | `src/ingest/pipeline.py` |
| [x] | CLI/脚本：一键摄入 `data/sample/` | `scripts/ingest_sample.py` |
| [x] | 上传目录约定与说明 | `data/uploads/.gitkeep` |

**阶段验收**：样例 MD（及 PDF）导入成功，可列出 `doc_id` / 路径。

---

## 2. 切分 · Embedding · 向量检索 — `src/rag/` `indexes/`

| 状态 | 任务 | 路径 |
|------|------|------|
| [x] | 递归分块 + MD 按标题切分；块元数据：`source`/`heading_path`/`page`/`doc_id` | `src/rag/chunking.py` |
| [ ] | （Should）父子分块：`parent_id` | `src/rag/chunking.py` |
| [x] | Embedding 客户端封装（模型名写入索引元数据） | `src/rag/embeddings.py` |
| [x] | Chroma 写入/查询（余弦；持久化 `indexes/chroma`） | `src/rag/vectorstore.py` |
| [x] | 检索服务：`recall_k`；返回 text + metadata + score | `src/rag/retriever.py` |
| [x] | BM25 索引 + 与向量 RRF 融合 | `src/rag/bm25.py`, `src/rag/hybrid.py` |
| [x] | Rerank API（可选；无 Key 时跳过） | `src/rag/hybrid.py` |
| [x] | 上下文拼接、引用块头、`[n]` 校验、拒答模板 | `src/rag/generate.py` |

**阶段验收**：仅 RAG（无 Agent）能回答 3 道纯检索题并带引用。

---

## 3. 工具 — `src/tools/`

| 状态 | 任务 | 路径 |
|------|------|------|
| [x] | `calculator`：安全表达式计算 | `src/tools/calculator.py` |
| [x] | `get_current_time`：日期时间星期 | `src/tools/time_tool.py` |
| [x] | 工具注册表 + OpenAI tool schema 导出 | `src/tools/registry.py` |
| [x] | （Should）`find_indexed_file` | `src/tools/file_query.py` |

**阶段验收**：脱离 Agent，单测/脚本可直接调用两工具得到正确结果。

---

## 4. Agent 循环与 Trace — `src/agent/` `traces/` `src/main.py`

| 状态 | 任务 | 路径 |
|------|------|------|
| [x] | 系统 Prompt：何时 retrieve / tool / 拒答；禁止用外部知识冒充文档 | `src/agent/prompts.py` |
| [x] | Agent 循环：最多 N 步；动作 `retrieve` \| `tool` \| `finish` | `src/agent/loop.py` |
| [x] | 将「知识库检索」注册为可调工具（或显式 action） | `src/agent/loop.py` / `src/tools/registry.py` |
| [x] | Trace：reasoning 摘要、action、input、observation 摘要、最终答案 | `src/agent/trace.py` → `traces/*.json` |
| [x] | （Should）Streamlit UI：对话 / 知识库 / Trace | `app/streamlit_app.py` |

**阶段验收**：纯工具题、混合题、拒答题各至少 1 道动作序列正确，且有 trace。

---

## 5. 评估 — `tests/` `scripts/run_eval.py`

| 状态 | 任务 | 路径 |
|------|------|------|
| [x] | ≥20 题题面（含期望动作、金标来源） | `tests/eval_questions.json` |
| [x] | 评估跑题脚本（可先半自动：打印模型路径，人工填表） | `scripts/run_eval.py` |
| [x] | 结果表：检索是否命中、动作是否正确、忠实/拒答、备注 | `tests/eval_results.md` |
| [x] | 至少 3 条失败 case 分析写入结果表 | `tests/eval_results.md` |

**阶段验收**：F7 + 验收标准 A3 材料齐全。

---

## 6. 答辩材料（不写代码也可先起草）

| 状态 | 任务 | 路径 |
|------|------|------|
| [x] | README 中解释 RAG 完整链路（对照本仓库目录） | `README.md` |
| [x] | README 中解释工具调用 vs 普通函数调用（配一条真实 trace） | `README.md` |
| [x] | Prompt 设计说明章节（强制） | `README.md` |

---

## 建议实施顺序（对照 Phase）

1. **Phase 0**：完成本文件「§0」剩余项 + 生成 PDF  
2. **Phase 1**：§1 + §2（先单路向量，不做 BM25/Rerank）  
3. **Phase 2**：§3 + §4  
4. **Phase 3**：§2 Should + §5 跑满 20+ 题 + §6  

---

## 完成定义（MVP Done）

- [x] MD / PDF 均可导入并检索  
- [x] Agent 能决定是否检索、是否调工具  
- [x] ≥2 工具可用；引用 + 拒答生效  
- [x] 每问有 trace  
- [x] `eval_questions.json` ≥20 题已跑并留下评估与失败分析  

（可选未做：父子分块；Rerank 需自备 API Key 后打开开关）
