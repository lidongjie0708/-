# BlogsLike

基于 Spring Boot + MySQL + Redis + RabbitMQ + Vue 3 构建的博客社区平台，支持文章、评论、点赞等核心业务；通过 FastAPI + RAG + LangGraph + Qdrant 扩展博客知识库问答、运营分析 Agent 与运营动作闭环。

主要能力：

- **点赞链路**：Redis Lua 原子计数、RabbitMQ 异步落库、批量 flush 与对账、计数实时展示。提交说明见 [docs/GIT_COMMIT.md](docs/GIT_COMMIT.md)。
- **RAG 知识问答**：混合检索（Qdrant + BM25 + RRF）、两级精排、检索 Trace、三层会话记忆与答案缓存，回答均带文章引用。
- **运营分析 Agent**：管理员自然语言问数 → LangGraph 编排的安全只读 SQL 分析 → 图表/报告/建议；带证据的运营发现、动作提案与人工审批闭环。

功能简介、本地启动与验证方法见 [docs/BlogsLike_RAG与Agent功能介绍与操作指南.md](docs/BlogsLike_RAG与Agent功能介绍与操作指南.md)。

## 目录

- `src/`：Spring Boot 后端（Java 17）
- `python/`：FastAPI + LangGraph Agent 服务（含 RAG 流水线）
- `thumb-front/`：Vue 3 前端
- `sql/migration/`：Flyway 顺序迁移
- `load-tests/k6/`：点赞/RAG/运营 k6 压测脚本
- `evals/`：RAG 与 Agent 评测/基准
