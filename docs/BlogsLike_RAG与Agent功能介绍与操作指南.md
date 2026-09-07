# BlogsLike：点赞优化 · RAG 问答 · 运营分析 Agent 功能介绍与操作指南

> 适用读者：需要快速了解本项目智能能力、复现运行、或把代码讲清楚的开发者。
> 详细的实现级讲解见《RAG与运营分析Agent代码讲解.md》；点赞性能优化背景见 `docs/GIT_COMMIT.md`。

## 1. 系统概览

BlogsLike 是包含三个服务的博客平台：

| 服务 | 技术栈 | 职责 |
| --- | --- | --- |
| Java 后端（`src/main/java`） | Spring Boot + MySQL + Redis + RabbitMQ | 博客/评论/点赞等核心业务，Agent token 签发、运营动作命令与审批、Outbox 异步事件、观测指标 |
| Agent 服务（`python/`） | FastAPI + LangGraph + Qdrant + Redis + MySQL | RAG 知识问答、运营分析 Agent、多 Agent 路由与记忆沉淀 |
| 前端（`thumb-front/`） | Vue 3 + Vite | 博客前台、AI 助手、RAG 知识库工作台、运营中心 |

核心链路有三条：

1. **点赞链路**：Redis Lua 原子计数 + RabbitMQ 异步落库 + 批量 flush + 对账/刷新任务 + 实时计数读取。
2. **RAG 链路**：文章写入后异步向量同步 → 用户提问 → 会话记忆 → 混合检索 → 精排 → 生成带引用答案 → 观测与评测。
3. **Agent 链路**：管理员用自然语言提问 → 运营分析 Agent 路由到模板 SQL/受控工具循环 → 安全只读执行 → 输出图表与报告；运营动作经提案 → 审批 → Outbox → 幂等执行闭环。

## 2. 本次提交包含什么

### 2.1 RAG 知识问答增强

`python/app/rag/` 与 `python/app/agents/rag_qa_agent.py`：

- **检索前权限过滤**：Qdrant 候选阶段按角色/可见范围过滤，普通用户只检索 `PUBLIC`，管理员可含 `PRIVATE` 与草稿，避免敏感内容进入 Prompt 后再遮挡。
- **混合检索 + 两级精排**：向量召回（Qdrant）+ BM25 关键词召回，RRF 融合；本地粗排不确定时才调用远程 Rerank，控制成本与延迟。
- **检索 Trace**：`retrievalTrace` 记录改写、各阶段候选与过滤原因，支撑“为什么检索到这篇文章”的可排查性。
- **三层会话记忆**：Redis 短期窗口 + MySQL 原始轮次 + 异步结构化长期摘要（V2.9.0），LLM 不可用时写降级摘要。
- **答案缓存**：精确/语义双层缓存（V2.8.0 拆分观测与评测表），命中时跳过检索与生成。
- **观测与评测**：`agent_analysis_log`/`rag_evaluation_log` 写入调用链路；`evals/` 提供 RAG 评测与线上 Agent 基准脚本。

### 2.2 运营分析 Agent（LangGraph）

`python/app/agents/analytics_agent.py`（约 90KB，含 LangGraph 状态机）、`operations_agent.py`、`analytics_memory.py`、`python/app/ops_metrics/`、`python/app/tools/`：

- **权限与安全**：仅 ADMIN 可调用；SQL 只读校验（仅 SELECT、强制 LIMIT、禁 `select *`、禁写库），`validate_readonly_sql`/`sql_safety_check_tool` 双保险。
- **规则优先意图识别**：7 类模板意图先走规则匹配（阈值 0.75），不满足再让 LLM 分类，省 token 且可确定性降级；模板 SQL 失败时回退 LLM 工具路径。
- **带证据的运营发现**：内容互动下滑、评论风险、内容供给缺口三类受治理指标，返回指标版本、当前/基线窗口、样本量、z 分数、数据新鲜度与局限性；样本不足只降级为 `INSUFFICIENT_DATA`，不下结论。
- **记忆与上下文分层**：L0-L4 分层组装、短期轮次压缩、异步长期记忆沉淀（`python/app/agents/prompts/` 提供提示词模板）。
- **流式事件**：`/analytics/query/stream` SSE 输出 status/plan/sql/memory/result，前端运营中心按事件渐进渲染。

### 2.3 运营动作闭环（Java + Python 配合）

Java 侧新增（`Operation*Controller`/`Service`/`Mapper`/`Entity`，迁移 V2.10.0、V2.11.0、V2.13.0、V2.14.0）：

- **动作提案**：管理员创建受白名单约束的动作（如 SEO 改稿草稿），高风险动作必须审批；幂等键保护重复提交。
- **审批与执行**：审批人不可审批自己的提案；通过后写 Outbox → RabbitMQ 投递 → 幂等执行。
- **效果观测**：`operation_finding`、`operation_experiment`、`operation_action` 记录观察窗口与前后指标；`/agent/operations/findings`、`/agent/operations/actions/{id}/observations` 只读查询。
- **每日报告**：运营日报生成与查询接口（`/operations/daily-reports`）。

Agent Outbox 发布器同步升级：批量拉取、并发发布、publisher confirm 确认、失败/死信指标埋点。

### 2.4 前端与数据库

- 前端新增 `/agent/operations` 运营中心（自然语言运营助手 + 异常诊断 + 历史日志），并保留原 AI 助手（RAG/聊天/运营多模式）与管理后台入口。
- 新增 Flyway 迁移：`V2.8.0`（拆分 RAG 观测与评测）、`V2.9.0`（异步结构化记忆摘要）、`V2.10.0`（operation_action）、`V2.11.0`（运营增长可观测）、`V2.13.0`（运营日报）、`V2.14.0`（ops 记忆条目）。
- 新增 Python/Java/前端测试与评测：`python/tests/`、`src/test/java/com/yuyuan/thumb/service/agent/AgentServiceTest.java`、`evals/*_benchmark.py`。

## 3. 本地启动与配置

### 3.1 依赖服务

| 服务 | 默认地址 | 用途 |
| --- | --- | --- |
| MySQL | `localhost:3306/thumb_db` | 业务与 Agent 数据 |
| Redis | `localhost:6380` | 点赞计数、会话记忆、缓存 |
| RabbitMQ | `localhost:5672` | 点赞/Agent Outbox 异步事件 |
| Qdrant | `localhost:6333` | RAG 向量库（collection `blog_chunks`） |

### 3.2 Java 后端

```powershell
mvn spring-boot:run
```

默认端口 `9199`，上下文 `/api`。环境变量可通过 `src/main/resources/application.yml` 覆盖。

### 3.3 Python Agent 服务

```powershell
cd python
uv sync
copy .env.example .env   # 填入 DASHSCOPE_API_KEY、JWT_SECRET 等
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

`python/README.md` 有完整的 `.env` 变量说明；迁移需在 MySQL 上按序执行 `sql/migration/`（Flyway 自动执行，手工执行时注意顺序 V2.8.0 → V2.14.0）。

### 3.4 前端

```powershell
cd thumb-front
npm install
npm run dev
```

Vite 代理：`/api → localhost:9199`（Java），`/py-agent → localhost:8001/api/agent`（Python）。

## 4. 功能验证

### 4.1 RAG 问答

1. 登录后前端进入「AI 助手」→ RAG 模式（或直接调用接口）。
2. 向 `/blog/create` 提交文章，Java 经 Agent token 调用 `/api/agent/execute` 触发向量同步。
3. 提问“点赞功能在 Redis 里怎么存储的？”应返回带 `[1]` 引用的答案与 `retrievalTrace`。

接口（Python，`/api/agent` 前缀）：

```text
POST /rag/ask                    # 非流式问答
POST /rag/ask/stream             # SSE 流式（status/citations/token/done）
POST /rag/evaluate               # 对测试用例跑评测
POST /execute                    # action=embed：同步文章进 Qdrant
```

### 4.2 运营分析 Agent

管理员登录后进入前端「运营中心」→ 运营助手，提问如：

```text
按点赞数统计热门博客，返回前 10 篇
```

页面会依次展示思考/计划/SQL/结论事件；也可以在「异常诊断」页选择场景运行受治理指标诊断。接口：

```text
POST /analytics/query            # 运营分析（仅 ADMIN）
POST /analytics/query/stream     # SSE 流式分析
GET  /analytics/logs/page        # 分析历史日志
POST /operations/analyze         # 三类受治理指标诊断
POST /operations/actions/preview # 动作提案预览（不落库、不执行）
```

### 4.3 点赞性能验证

见 [docs/GIT_COMMIT.md](GIT_COMMIT.md) 的验证脚本（k6 `load-tests/k6/`）与压测结果。

## 5. 测试与质量

```powershell
# Python（在 python/ 目录）
uv run pytest

# Java（Java 17）
mvn test

# 前端
cd thumb-front; npm run build
```

关键测试覆盖：

- `python/tests/test_analytics_*`：LangGraph 节点路由、流式事件顺序、结构化执行、模板降级与成本控制；
- `python/tests/test_operations_agent.py`、`test_ops_metrics_diagnostics.py`：证据完整性、样本不足不下结论、指标版本；
- `python/tests/test_operation_actions.py`、`test_operation_action_routes.py`：动作白名单、预览无副作用、仅 ADMIN；
- `python/tests/test_memory_summary.py`、`test_analytics_memory.py`：记忆摘要 schema、上下文分层预算；
- `src/test/java/com/yuyuan/thumb/service/agent/AgentServiceTest.java`：Agent 字段回写不覆盖用户编辑；
- `evals/`：RAG 场景与线上 Agent 基准、召回与分析一致性。

## 6. 目录索引

| 主题 | 位置 |
| --- | --- |
| RAG 实现 | `python/app/rag/`、`python/app/agents/rag_qa_agent.py` |
| 运营分析 Agent | `python/app/agents/analytics_agent.py`、`operations_agent.py` |
| 动作闭环（Java） | `src/main/java/com/yuyuan/thumb/controller/Operation*`、`service/Operation*` |
| 提示词与上下文分层 | `python/app/agents/prompts/` |
| 迁移 | `sql/migration/V2.8.0__*.sql` ~ `V2.14.0__*.sql` |
| 前端页面 | `thumb-front/src/views/OperationsCenter.vue`、`UnifiedAgent.vue`、`RagKnowledgeBase.vue` |
| 深度讲解 | 仓库根目录《RAG与运营分析Agent代码讲解.md》 |
| 点赞提交说明 | `docs/GIT_COMMIT.md` |
