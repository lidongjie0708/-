# Java 全链路测试

这套测试验证：

`MockMvc HTTP → Spring Security/JWT → Controller → Service/MyBatis → MySQL → Redis/Redisson → RabbitMQ → Java Consumer → Python Agent → 数据回写`

## 分层

### 默认 Maven 测试

```powershell
$env:JAVA_HOME='D:\jdk17'
$env:Path='D:\jdk17\bin;' + $env:Path
mvn test
```

默认测试不会连接开发数据库，也不会再执行旧测试中的“插入五万用户”逻辑。

### 隔离环境全链路 E2E

前置条件：

- Docker Desktop 可用；
- Python Agent 已在 `8001` 启动；
- Python 依赖的 Qdrant 可用；
- 测试镜像 `mysql:8.0`、`redis:7-alpine`、`rabbitmq:3-management` 可拉取。

执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tests\java-e2e\run-e2e.ps1
```

脚本会：

1. 检查 Python Agent；
2. 启动隔离的 MySQL `13306`、Redis `16379`、RabbitMQ `25672`；
3. 初始化专用 `thumb_e2e` 数据库；
4. 只运行 `JavaFullChainE2ETest`；
5. 验证登录、资料、Markdown 博客、评论、独立回复、点赞、管理员、Agent Token；
6. 等待 RabbitMQ 消费者调用 Python Agent，并验证博客及评论分析结果回写；
7. 删除测试数据并关闭容器。

调试时保留容器：

```powershell
.\tests\java-e2e\run-e2e.ps1 -KeepInfrastructure
```

## CI 建议

- Pull Request：运行 `mvn test` 和 MockMvc 集成测试。
- 合并主分支：运行隔离基础设施 E2E。
- 发布前：再运行 `tests/system/smoke.ps1`，验证真实部署地址。
- E2E 失败时保留 RabbitMQ 死信、Java 日志和 Python Agent 日志作为构建产物。

不要把 E2E 指向 `thumb_db`。测试默认使用独立的 `thumb_e2e`。
