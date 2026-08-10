# RAG + Tool Calling Agent

从 0 到 1：导入 Markdown / PDF → 切分与向量检索 → Agent 按需检索或调用工具 → 引用来源 / 证据不足拒答 → 记录每步 Trace → 用 ≥20 题评估。

- 技术栈：[docs/TECH_STACK.md](docs/TECH_STACK.md)
- 任务清单：[docs/TASKS.md](docs/TASKS.md)
- 评估题：[tests/eval_questions.json](tests/eval_questions.json)
- Prompt 规范：[README-Prompt规范.md](README-Prompt规范.md)

## 当前进度

| 阶段 | 状态 |
|------|------|
| Phase 0 配置与语料契约 | 已完成 |
| Phase 1 RAG 闭环 | 已完成 |
| Phase 2 Agent + 工具 | 已完成（calculator / time / retrieve + Trace） |
| Phase 3 评估增强 | 未开工 |

## 快速准备（Phase 0）

```powershell
# 推荐：Python 3.13 + 项目内 .venv（勿用全局 pip）
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Phase 3 增强（可选）：.\.venv\Scripts\python.exe -m pip install -r requirements-optional.txt
copy .env.example .env   # 填入 LLM_API_KEY / EMBEDDING_API_KEY 等
```

旋钮见 `configs/default.yaml`（`recall_k=20`、`final_k=5`、`chunk_size` 等）。

## 目录职责（构建时对照）

| 目录 | 职责 |
|------|------|
| `data/sample` | 冻结评估语料 |
| `src/ingest` | 加载 MD/PDF，触发入库 |
| `src/rag` | 切分、Embedding、检索、拼接与引用 |
| `src/tools` | 计算器、时间等工具函数 + schema |
| `src/agent` | 决策循环与 Trace |
| `indexes/chroma` | 向量持久化 |
| `traces` | 每问运行轨迹 |
| `tests` | 考题与结果表 |

---

## Prompt 设计说明

> 下列为 **MVP 设计约定**。代码落地后请把「计划路径」改成真实文件中的常量/函数名，并补齐迭代对比的实测数据。

### Prompt 结构

| 结构 | 是否使用 | 说明 | 计划位置 |
|------|----------|------|----------|
| System Prompt | 是 | 角色、检索/工具/拒答边界 | `src/agent/prompts.py` |
| User Prompt 模板 | 是 | 用户问题；RAG 阶段含检索块 | `src/agent/prompts.py` / `src/rag/generate.py` |
| 角色设定（Role） | 是 | 个人知识库问答助手 | System 内 |
| 任务描述（Task） | 是 | 按需 retrieve / tool / finish | System + tool schema |
| 上下文（Context） | 是 | 检索片段、工具 observation、历史 step | Agent 消息列表 |
| 输出约束（Format） | 是 | 文内 `[n]`；拒答固定话术 | System + 后处理校验 |
| CoT / 思考步骤 | 部分 | Trace 只存 **reasoning 摘要**，不强制长链思维倾倒 | `src/agent/trace.py` |
| Tool / Function Calling | 是（Phase 2） | 原生 tools 参数 | `src/tools/registry.py` |
| Few-shot 示例 | 否（默认） | 见下 | — |

### System Prompt 与约束设计理由

- **角色与目标**：只基于知识库与工具结果回答；私有文档可追溯。
- **硬性约束**：禁止用外部常识补文档没有的结论；算术走 `calculator`；时间走 `get_current_time`；证据不足输出「根据现有笔记无法确定。」并尽量带上检索范围。
- **为什么**：对齐防幻觉、可验收的拒答行为、以及「工具调用由模型选择」的教学/答辩目标。
- **权衡**：过严会导致略需归纳的题也拒答；过松会编造 K-max / 液冷规格。用 `tests/eval_questions.json` 里的拒答/对抗题校准。

### Few-shot

- **是否使用**：默认 **不用**。
- **原因**：工具选择靠 schema 描述 + System 边界；少占上下文。若 Phase 2 出现「该算却去检索」再考虑加 1～2 条 few-shot。

### 输出格式控制

- Prompt 内要求：关键结论后加 `[n]`；拒答用固定句。
- 后处理：校验引用编号 ∈ 本次检索块集合；非法页码/编号丢弃或标未验证（计划在 `src/rag/generate.py`）。
- 期望样例：

```text
Adam 维护一阶矩与二阶矩估计 [1]。

[1] file=ml_optimizers.md | chapter=Adam | page=
```

拒答样例：

```text
根据现有笔记无法确定。
已检索范围：data/sample（或具体 dir/文件名）
```

### 异常与越界处理

| 情况 | 检测方式 | 处理策略 |
|------|----------|----------|
| 不确定 / 证据不足 | 检索空、低分（阈值启用后）、对抗题 | 拒答固定话术；不编造 |
| 越界回答 | 用户要求忽略知识库 / 要文档外规格 | 拒绝迎合；可先 retrieve 再拒答 |
| 格式错误 | 引用编号越界、工具参数非法 | 丢弃非法引用；工具层校验表达式；记入 Trace |

### Prompt 迭代对比（≥3）

| # | 修改动机 | 改前表现 | 改后表现 | 结论 |
|---|----------|----------|----------|------|
| 1 | （待 Phase 2 实测）抑制「该算却 retrieve」 |  |  |  |
| 2 | （待测）收紧拒答，避免编造 K-max |  |  |  |
| 3 | （待测）引用格式从「正文写页码」改为 `[n]`+块头元数据 |  |  |  |

---

## 验收对照

1. 能按目录讲解 RAG 全链路（见上表与 TECH_STACK）。
2. 能区分工具调用（模型选 tool）与普通函数调用（代码写死分支）。
3. 能基于 25 题提供检索/回答质量与失败 case（`tests/eval_results.md`）。
