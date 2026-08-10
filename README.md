# RAG + Tool Calling Agent

从 0 到 1：导入 Markdown / PDF → 切分与向量检索（可选 BM25 混合）→ Agent 按需检索或调用工具 → 引用来源 / 证据不足拒答 → 记录每步 Trace → 用 ≥20 题评估。

- 技术栈：[docs/TECH_STACK.md](docs/TECH_STACK.md)
- 任务清单：[docs/TASKS.md](docs/TASKS.md)
- 评估题：[tests/eval_questions.json](tests/eval_questions.json)
- Prompt 规范：[README-Prompt规范.md](README-Prompt规范.md)

## 当前进度

| 阶段 | 状态 |
|------|------|
| Phase 0 配置与语料契约 | 已完成 |
| Phase 1 RAG 闭环 | 已完成 |
| Phase 2 Agent + 工具 | 已完成 |
| Phase 3 混合检索 + 评估 | 已完成（BM25+RRF、run_eval、答辩说明；Rerank 可选） |

## 环境准备

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-optional.txt
copy .env.example .env   # 填入 LLM / Embedding Key；聊天与向量网关常不同
```

常用命令：

```powershell
.\.venv\Scripts\python.exe -m src.main ingest-sample
.\.venv\Scripts\python.exe -m src.main ask "你的问题" --show-steps
.\.venv\Scripts\python.exe -m src.main ask "..." --rag-only
.\.venv\Scripts\python.exe -m src.main show-trace
.\.venv\Scripts\python.exe scripts\run_eval.py --mode agent
```

旋钮见 `configs/default.yaml`（`hybrid.enabled`、`recall_k=20`、`final_k=5` 等）。

## 目录职责（对照 RAG 全链路）

| 目录 / 文件 | 在链路中的位置 |
|-------------|----------------|
| `data/sample` | 离线语料 |
| `src/ingest/loaders.py` | 文档加载与解析（MD/PDF） |
| `src/rag/chunking.py` | 分块策略 |
| `src/rag/embeddings.py` | Embedding |
| `src/rag/vectorstore.py` + `bm25.py` | 向量索引 + 关键词索引 |
| `src/rag/retriever.py` + `hybrid.py` | 召回与 RRF 融合（可选 Rerank） |
| `src/tools/*` | 计算器 / 时间等工具函数 |
| `src/agent/loop.py` | 在线决策：是否检索、是否调工具 |
| `src/rag/generate.py` | Phase1 固定生成；Agent 最终回答在 loop 内完成 |
| `src/agent/trace.py` | 每步 reasoning / 工具 / 终态 |
| `tests/` | 评估题与结果 |

### RAG 完整链路（答辩口述）

**离线**：加载解析 → 元数据（source/heading/page）→ 切分 → Embedding 写入 Chroma → 同步 BM25 语料。  
**在线（Agent）**：问题 → 模型选工具 → `retrieve_knowledge`（向量∪BM25→RRF→Top-K）和/或 `calculator` / `get_current_time` → observation 回灌 → 最终回答（引用或拒答）→ Trace。  
**旁路**：`scripts/run_eval.py` 跑 `eval_questions.json`。

### 工具调用 vs 普通函数调用（答辩口述）

| | 普通函数调用 | 本项目的工具调用 |
|--|--------------|------------------|
| 谁决定调用 | 开发者写死 `if/else` 或固定顺序 | **模型**根据题意与中间结果选择 |
| 何时调用 | 编码时已定 | **运行时**多步决策（见 Trace） |
| 参数 | 代码传入 | 模型填充 JSON（`src/tools/registry.py`） |
| 失败 | try/except 固定逻辑 | observation 回灌，可改策略或拒答 |

检索也是一种工具：`retrieve_knowledge`，不是写死「每问必搜」。可用 `ask --show-steps` 或 `show-trace <id>` 演示。

---

## Prompt 设计说明

### Prompt 结构

| 结构 | 是否使用 | 说明 | 代码位置 |
|------|----------|------|----------|
| System Prompt | 是 | 角色、检索/工具/拒答边界 | `src/agent/prompts.py`；Phase1 另见 `src/rag/generate.py` |
| User Prompt | 是 | 用户问题；工具结果在 messages 中 | `src/agent/loop.py` |
| 角色设定 | 是 | 个人知识库 Agent | System |
| 任务描述 | 是 | 按需 retrieve / tool / finish | System + tool schema |
| 上下文 | 是 | 检索 JSON、工具返回、历史 step | Agent messages |
| 输出约束 | 是 | `[n]` 引用；拒答话术 | System + 后处理脚注 |
| CoT | 部分 | Trace 存摘要，不倾倒长思维链 | `src/agent/trace.py` |
| Tool Calling | 是 | OpenAI 兼容 tools | `src/tools/registry.py` |
| Few-shot | 否 | 见下 | — |

### System Prompt 与约束设计理由

- **目标**：私有文档可追溯；算术/时间走确定性工具。
- **硬约束**：禁止外部常识冒充笔记；文档题先检索；不足则「根据现有笔记无法确定。」
- **原因**：防幻觉、可验收、能讲清「模型编排工具」。
- **权衡**：过严会拒答可归纳题；过松会编造 K-max/液冷。用评估题校准。

### Few-shot

默认 **不用**。工具选择依赖 schema + System；若出现「该算却 retrieve」再加 few-shot。

### 输出格式控制

- Prompt 要求 `[n]`；retrieve 结果自带 `formatted` 块头。
- Agent 结束时按引用编号补「来源」脚注（`src/agent/loop.py`）。
- 计算器禁止任意 `eval`（AST 白名单，`src/tools/calculator.py`）。

### 异常与越界处理

| 情况 | 检测 | 策略 |
|------|------|------|
| 证据不足 / 未定义 | 检索空或笔记写明未定义 | 拒答话术 / 等价表述 |
| 越界（忽略知识库） | 对抗题 + Prompt | 拒绝迎合 |
| 工具参数错误 | registry 捕获 | 返回 error JSON 给模型 |

### Prompt 迭代对比（≥3）

| # | 修改动机 | 改前表现 | 改后表现 | 结论 |
|---|----------|----------|----------|------|
| 1 | 抑制纯算术走检索 | 仅笼统说「可调用工具」 | 明确「纯算术只 calculator」后，T01 稳定走计算器 | schema+边界句比空泛角色有效 |
| 2 | K-max 勿编造定义 | 只说证据不足要拒答 | 补充「笔记写明未定义也要无法确定」 | 拒答要覆盖「显式未定义」 |
| 3 | 引用可校验 | 模型在正文写页码易幻觉 | 统一 `[n]` + 块头 metadata 脚注 | 页码来自入库字段更可辩护 |

---

## 验收对照

1. 能按上表讲解 RAG 全链路。  
2. 能结合 Trace 区分工具调用与普通函数调用。  
3. 评估结果见 `tests/eval_results.md`（由 `scripts/run_eval.py` 生成）。
