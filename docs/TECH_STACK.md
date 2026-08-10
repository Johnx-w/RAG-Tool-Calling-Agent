# 技术栈（已冻结 · MVP）

> 变更技术栈需同步更新本文件，并重跑 `tests/eval_questions.json` 全量题。

## 总览


| 层                  | 选型                                                           | 版本约束                              |
| ------------------ | ------------------------------------------------------------ | --------------------------------- |
| 语言                 | Python                                                       | 3.11+                             |
| 包管理                | `pip` + `requirements.txt`（可选 `requirements-optional.txt`） | 核心与 Phase3 增强拆分；用 venv 内 `python -m pip` |
| LLM / Tool Calling | OpenAI 兼容 API（推荐 GPT-4.1-mini / gpt-4o-mini 级，以账号可用为准）       | 必须支持 **原生 function/tool calling** |
| Embedding          | OpenAI 兼容 Embedding（推荐 `text-embedding-3-small`）             | 换模型 = 全量重嵌 + 阈值重标                 |
| Rerank（Should）     | Cohere Rerank 或 Jina Rerank API                              | MVP Must 可先不上                     |
| 编排                 | **自研轻量 Agent 循环**（`src/agent/`）                              | 不用重型多 Agent 框架；便于验收口述             |
| 文档解析               | Markdown：自研/正则标题；PDF：`pymupdf`（PyMuPDF）                      | 扫描件 OCR 不做                        |
| 切分                 | `src/rag/chunking.py`：MD 按标题；通用递归分块；Should：父子                | overlap 10%–20%                   |
| 向量库                | **Chroma**（持久化到 `indexes/chroma/`）                           | 小数据等价精确检索即可                       |
| 关键词（Should）        | `rank_bm25` + 中文分词 `jieba`                                   | 与向量 RRF 融合                        |
| 配置                 | `pydantic-settings` + `.env`                                 | 密钥不入库                             |
| CLI                | `typer`                                                      | MVP 主入口                           |
| UI（Should）         | Streamlit                                                    | 不挡 CLI 验收                         |
| 日志 / Trace         | JSONL → `traces/`                                            | 见字段约定                             |
| 评估                 | `tests/eval_questions.json` + 人工/脚本填 `tests/eval_results.md` | ≥20 题                             |




## 明确不用（MVP）

- LangGraph / 多 Agent 框架（避免「能跑但讲不清」）
- Milvus / Pinecone（过重）
- 本地部署大模型、自训 Embedding
- OCR、Word 专有格式（项目只要求 MD/PDF）
- GraphRAG



## 两个 Must 工具


| 工具名                | 实现位置                      | 说明                       |
| ------------------ | ------------------------- | ------------------------ |
| `calculator`       | `src/tools/calculator.py` | 安全四则/表达式（禁止 `eval` 任意代码） |
| `get_current_time` | `src/tools/time_tool.py`  | 返回本地时区日期时间与星期            |


Should 第三工具：`find_indexed_file`（在已导入文档元数据中按文件名查询）。

## 环境变量（`.env.example`）

```text
LLM_API_KEY=
LLM_BASE_URL=          # 可选，兼容网关
LLM_MODEL=
EMBEDDING_API_KEY=     # 可与 LLM 相同
EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PATH=indexes/chroma
# COHERE_API_KEY=      # Should：Rerank
```



## 与验收的关系

- **RAG 链路**：全部落在 `src/ingest` + `src/rag`，可用 CLI 单独跑通。
- **工具调用**：`src/agent` 通过 API tool schema 暴露工具；对比「普通函数调用」时指这里由模型选 tool。
- **评估**：只认 `tests/eval_questions.json` 题面与 `data/sample/` 语料契约。

