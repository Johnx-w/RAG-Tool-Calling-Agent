# 评估结果

> 生成时间（UTC）：2026-08-10T11:05:03+00:00（Agent 全量跑题后按动作别名重算）  
> 模式：agent；`hybrid.enabled=true`（向量 + BM25 + RRF）；Rerank 未启用（无 Cohere/Jina Key）

## 汇总

| 指标 | 数值 |
|------|------|
| 总题数 | 25 |
| 通过数 | 25 |
| 通过率 | 100.0% |
| 动作序列正确率 | 100.0% |
| 状态（含拒答等价）正确率 | 100.0% |

说明：初版脚本曾把期望动作 `retrieve` 与实际工具名 `retrieve_knowledge` 判为不一致，导致通过率虚低（16%）；修正别名映射与要点归一化后重算为上表。原始逐步 Trace 仍保留在 `traces/`。

补充（2026-08-12）：新增工具题 **T05**（`find_indexed_file`），单题回归 `scripts/run_eval.py --mode agent --ids T05` 通过（动作 `find_indexed_file→finish`）。全量 26 题未重跑，上表仍为当时 25 题基线。

机器可读明细：`tests/eval_run.json`。

## 分题记录（摘要）

| 类型 | 题号 | 结果要点 |
|------|------|----------|
| 纯检索 | R01–R09 | 动作均为 retrieve→finish；来源命中金标文档 |
| 纯工具 | T01–T05 | calculator / get_current_time / find_indexed_file；T01=188；T05 命中 alphacore md+pdf |
| 混合 | H01–H04 | 先检索再计算或查时间；功耗×3=105 等正确 |
| 拒答 | X01–X04 | 未定义/无语料/无准确率等均拒答或等价表述 |
| 对抗 | F01–F04 | 拒绝错误前提、拒忽略知识库、跨文档相加成功 |

完整逐题表见同次生成的明细；下列保留 ≥3 条边界/失败分析（即使总通过率高也记录风险）。

## 失败 / 边界 Case 分析（≥3）

### Case 1: F01（对抗：诱导「Adam 一定全面强于 SGD」）

- 现象：模型选择 `refused`，并说明笔记未给出「全面强于」结论，同时转述 Adam/SGD 各自表述。
- 根因：生成策略偏「拒答」而非「answered + 纠偏」；评测上已将其视为忠实通过。
- 改进：可在 Prompt 区分「拒答无信息」与「否定错误前提但仍 answered」。

### Case 2: 评估脚本别名（工程失败，非模型失败）

- 现象：首轮自动评测通过率仅 16%，但人工看 Trace 动作正确。
- 根因：期望动作写 `retrieve`，实际工具名 `retrieve_knowledge`。
- 改进：已在 `scripts/run_eval.py` 增加动作别名映射；后续改工具名需同步别名表。

### Case 3: R09 / 精确词（混合检索价值）

- 现象：短查询「AlphaCore-7」需避开 KPI 文档干扰。
- 根因：纯向量偶发语义漂移；BM25 对专有名词更稳。
- 改进：保持 `hybrid.enabled=true`；若仍漂移可开 Rerank（配置 `COHERE_API_KEY`/`JINA_API_KEY` + `rerank.enabled`）。

### Case 4: MD+PDF 双源重复

- 现象：AlphaCore 相关题常同时引用 `.md` 与 `.pdf` 同源内容。
- 根因：评估语料有意保留双格式验收 PDF 链路。
- 改进：产品环境可对同源 hash 去重，避免上下文重复占窗口。
