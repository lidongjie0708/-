# 点赞系统性能优化 — 提交说明

本文档记录本次提交涉及的改动、原因、数据库变更与验证结果，便于回看与面试讲解。

## 一、提交范围

本次提交为点赞系统一组相互关联的性能优化：JWT 身份零查询、请求路径零 DB、计数批量聚合落库、对账收口、计数展示实时化，以及配套的观测埋点、测试与压测脚本。

## 二、变更内容

### 1. JWT 身份零查询

- `JwtUtil`：token 增加 `userId` / `role` claim，新增 `parseToken()`，复用缓存的 `JwtParser` 单例（修复 jjwt ServiceLoader 每请求扫描导致的 JarFile 锁竞争）。
- `JwtAuthenticationFilter`：从 claim 构造 `LoginUser`，不再 `loadUserByUsername` 查库。
- 新增 `LoginUser`（实现 `Principal`）、`UserContext`（当前用户线程上下文）。
- `UserServiceImpl.getLoginUser`：Caffeine 本地缓存（5 分钟 TTL，改资料失效）。

### 2. 请求路径零 DB + MQ 异步落库

- `ThumbServiceRabbitMQImpl`：点赞/取消只做 Redis Lua（V2 脚本）+ 直发 RabbitMQ，去掉同步 outbox 写入与事务；发送失败回滚 Redis 状态补偿。
- `RabbitMQConfig`：publisher confirm + returns 回调，路由失败不再静默丢失。
- `RabbitThumbConsumer`：按 Redis 当前点赞状态投影 MySQL（insertIgnore / delete），配合 `uk_user_blog` 唯一索引幂等，乱序/重复消息可收敛。

### 3. 计数批量聚合落库（本次核心）

- Lua 脚本内 `HINCRBY thumb:blog:delta` 原子聚合每篇博客的计数增量。
- `ThumbCountFlushJob`：
  - 每 5 秒 RENAME 双缓冲（`delta → delta:flushing`），flush 期间新增量不丢；
  - 按 `thumb.flush.batch-size`（默认 1000）分批执行 `CASE WHEN ... IN (...)` 批量 UPDATE；
  - Redisson 分布式锁保证多实例同时只有一个节点 flush；
  - batchId 在 RENAME 时原子写入 Redis，MySQL 侧 `thumb_flush_batch` 表 `INSERT IGNORE` 去重，覆盖"更新成功但删 key 前崩溃"的重试窗口；
  - 每 10 分钟清理 1 小时前的台账。
- 消费端不再逐事件 ±1，只维护关系表。

### 4. 对账收口

- `ThumbReconcileJob`：5 分钟对账改为可配置（`thumb.reconcile.cron`）；扫描 `thumb:*` 时跳过非纯数字后缀的 key，修复基准测试残留 key / delta key 导致的对账崩溃。
- 新增 `ThumbCountRefreshJob`：每日 03:30 从 thumb 表全量重建计数。

### 5. 计数展示实时化

- 展示计数 = MySQL `thumbCount` 基数 + Redis 未落库 delta，一次 `HMGET` 批量读取整页，点赞/取消后毫秒级生效，不再受 5 秒落库周期限制。
- `BlogService.fillRealTimeThumbCount(s)` + `BlogsController` 的 `/blog/all`、`/blog/my`、`/blog/{id}`。

### 6. 观测与压测

- 新增 metrics / monitor 埋点（点赞拦截、MQ 投递、缓存命中、对账差异等），Prometheus + Grafana 面板。
- k6 脚本：`likes.js`（写路径）、`likes-idempotency.js`（并发幂等）、`likes-only.js`（唯一点赞计数一致性）、`blog-page.js`（读路径）。

## 三、数据库变更

- `sql/migration/V2.12.0__create_thumb_flush_batch.sql`：新建 `thumb_flush_batch` 幂等台账表（batch_id 主键 + created_at 索引）。
- 本地 `thumb_db` 已执行该 DDL；`src/test/resources/e2e-schema.sql` 已同步。

## 四、验证结果

- `mvn test` 全部通过（含新增的 FlushJob 分批/幂等用例、实时计数用例等）。
- 批量落库：100 并发 36 秒产生 2.8 万事件，逐事件写需 2.8 万条 UPDATE，实际约 7 条批量语句、341 行更新（语句 -99.9%、行更新 -98.8%），MySQL 并发线程 ≤5。
- 多实例一致性：双实例（9199/9200）并发 flush，1,200 个唯一点赞后 `SUM(thumbCount)` 与 thumb 表行数完全一致（0 差异）。
- 实时计数：点赞后立即读详情计数=1（flush 未执行），取消后立即=0；30 并发读接口 211 req/s、p95 223ms，计数读取仅占每请求 Redis 命令的 4.8%。

## 五、未纳入本次提交

`python/`、`thumb-front/`、运营（Operation）功能、Agent 相关改动，以及日志与压测产物（`*.log`、`*.csv`、`reports/` 等）保持工作区状态，未提交。

## 六、如何验证

```powershell
# 启动
mvn spring-boot:run

# 写路径压测（50 VU，20s 稳定）
docker run --rm --cpuset-cpus=0-1 -e JAVA_BASE=http://host.docker.internal:9199/api `
  -e VUS=50 -e USERS=50 -e BLOGS=50 -e HOLD=20s -e RAMP_UP=3s -e RAMP_DOWN=3s `
  -v "${PWD}:/work" -w /work grafana/k6 run load-tests/k6/likes.js

# 计数一致性（唯一点赞，无重复）
docker run --rm -e JAVA_BASE=http://host.docker.internal:9199/api `
  -e VUS=30 -e USERS=30 -e BLOGS=50 -e ITER=40 `
  -v "${PWD}:/work" -w /work grafana/k6 run load-tests/k6/likes-only.js
```
