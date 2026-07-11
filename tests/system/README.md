# BlogsLike 全链路测试方案

## 1. 测试环境

仅在测试数据库和测试账号上执行写入与压测，禁止直接压生产数据库。

默认地址：

- Java API：`http://127.0.0.1:9199/api`
- Python Agent：`http://127.0.0.1:8001/api/agent`
- Web：`http://127.0.0.1:5173`

环境变量：

```powershell
$env:API_BASE_URL='http://127.0.0.1:9199'
$env:AGENT_BASE_URL='http://127.0.0.1:8001/api/agent'
$env:TEST_USERNAME='test_user'
$env:TEST_PASSWORD='change_me'
```

## 2. 执行顺序

1. Java、Python、前端、MySQL、Redis、RabbitMQ、Qdrant 全部启动。
2. 运行冒烟测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\tests\system\smoke.ps1
```

3. 在页面手工检查登录、文章 Markdown、评论回复、点赞、资料编辑、Agent SSE、管理日志详情。
4. 用 `agent-prompts.jsonl` 执行路由与回答质量评测。
5. 安装 k6 后逐级压测，先公共读，再登录业务，最后 Agent。

批量执行 Agent 提示词：

```powershell
$env:AGENT_TOKEN='replace_me'
powershell -ExecutionPolicy Bypass -File .\tests\system\run-agent-prompts.ps1 -Role USER
```

管理员 Token 使用 `-Role ADMIN`。脚本自动校验业务码和路由模式，回答内容仍需根据每条用例的 `assertions` 人工或使用评审模型评分。

## 3. 功能验收矩阵

| 模块 | 关键场景 | 验收标准 |
|---|---|---|
| 认证 | 登录、错误密码、登出、过期 Token | 状态码和业务码正确，无密码泄漏 |
| 用户 | 查询/编辑资料 | 只能编辑本人，邮箱校验生效 |
| 博客 | 新建、Markdown、详情、修改、删除 | 格式字段保留，非作者返回 403 |
| 评论 | 一级评论、独立回复、删除 | 回复挂载正确，跨博客父评论被拒绝 |
| 点赞 | 点赞、重复点赞、取消 | 幂等，计数最终一致 |
| RAG | 检索、引用、无答案、会话追问 | 引用可追溯，不编造知识库内容 |
| 运营 Agent | 排名、趋势、权限、SQL 安全 | 仅管理员可用，只执行只读 SQL |
| 自动路由 | chat/RAG/analytics/歧义 | 目标模式正确；歧义时澄清 |
| 管理台 | 筛选、分页、日志详情 | 大字段只在详情展示，分页稳定 |
| SSE | 首 Token、持续输出、完成事件、断线 | 事件顺序正确，无伪分块 |

## 4. 压测阶段

### 公共读接口

```bash
k6 run -e API_BASE_URL=http://127.0.0.1:9199 tests/system/k6-public.js
```

目标：先验证 20 VU，再提高到 50/100 VU。基线门槛：错误率 `<1%`，P95 `<500ms`。

### 登录业务流量

```bash
k6 run -e API_BASE_URL=http://127.0.0.1:9199 \
  -e TEST_USERNAME=test_user -e TEST_PASSWORD=change_me \
  tests/system/k6-authenticated.js
```

目标：P95 `<800ms`，错误率 `<1%`。脚本只压查询、点赞/取消，不批量制造文章。

### Agent 独立压测

先通过 `/agent/token` 获取短期 Agent Token：

```bash
k6 run -e AGENT_BASE_URL=http://127.0.0.1:8001/api/agent \
  -e AGENT_TOKEN=replace_me tests/system/k6-agent.js
```

Agent 初始只使用 1–3 VU。观察首 Token 时间、完整响应时间、模型限流、Qdrant/Redis/MySQL 连接池和费用。不要直接按普通 API 的 100 VU 压模型。

## 5. 监控指标

- HTTP：吞吐、P50/P95/P99、错误率、超时率。
- JVM：堆、GC、线程、Tomcat 工作线程、Hikari 连接池。
- MySQL：慢查询、连接数、锁等待、CPU、Buffer Pool 命中率。
- Redis：命中率、内存、阻塞客户端、命令延迟。
- RabbitMQ：积压、消费速率、重试和死信。
- Agent：路由模式、澄清率、首 Token、总耗时、Token 数、外部 API 429/5xx。
- RAG：召回为空比例、引用率、Top-K 分数、检索/重排/生成分段耗时。

停止条件：错误率超过 5%、数据库连接池耗尽、模型持续 429、P99 超过 10 秒或服务出现数据错误。
