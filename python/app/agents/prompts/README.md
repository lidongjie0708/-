# 运营助手提示词套件（Prompts Suite）

这套提示词对应「多 Agent + 长短记忆 + 上下文分层」架构，文件按角色拆分，便于单独加载、评测和迭代。

## 文件索引

| 文件 | 用途 | 加载时机 |
| --- | --- | --- |
| `supervisor.md` | 主管 Agent：意图理解、声明、路由、澄清、三段式结论 | 每次会话的系统提示 |
| `data_qa_agent.md` | 数据问答子 Agent：安全只读 SQL 生成与工具循环 | 路由到数据问答时 |
| `anomaly_diagnosis_agent.md` | 异常诊断子 Agent：健康指标对比与归因 | 路由到异常诊断时 |
| `memory_consolidator.md` | 记忆沉淀器：会话结束后回写长期记忆 | 会话结束时（异步） |
| `memory_retrieval.md` | 长期记忆召回：从候选记忆中按相关度选取注入项 | 每次组上下文前 |
| `short_term_memory.md` | 短期记忆维护：结构化轮次与压缩规则 | 读写 Redis 短期记忆时 |
| `context_layering.md` | L0-L4 上下文分层组装规范与预算 | 组装上下文时（构建器，非模型） |
| `intent_clarification.md` | 意图识别与澄清：固定意图分类、置信度、选项 | 意图节点 |
| `report_generation.md` | 报告生成：结论 + 依据 + 建议三段式 | 报告节点 |

## 上下文预算（默认值）

| 层 | 内容 | 预算 | 裁剪优先级 |
| --- | --- | --- | --- |
| L0 | 系统层：角色、安全规则、工具说明 | 不裁剪 | - |
| L1 | 长期记忆（跨会话） | ≤ 600 tokens | 最后裁，按 importance 降序保留 |
| L2 | 短期记忆（本会话轮次） | ≤ 800 tokens | 次之 |
| L3 | 即时层：问题、计划、查询结果 | 剩余预算 | 最先裁，先截大结果再截计划 |
| L4 | 输出层：格式与三段式约束 | 不裁剪 | - |

预算数值建议放到 `settings`（如 `analytics_context_budget`），方便压测时调参。

## 使用约定

- 所有提示词默认 UTF-8；向模型注入前用 `render(prompt, **state)` 填充占位符（`{{...}}`）。
- 模板结论、模板 SQL、规则意图识别属于工程降级层，不占用 LLM 提示词预算，见 `analytics_agent.py` 的 `TEMPLATE_INTENTS`。
- 长记忆写入依赖异步沉淀器，任何 LLM 失败都必须有本地降级，保证提示词缺失时链路仍可用。
