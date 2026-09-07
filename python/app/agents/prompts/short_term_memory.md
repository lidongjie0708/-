# 短期记忆维护（Short-term Memory）

## 任务

维护本会话的短期记忆（Redis）：结构化轮次、按预算压缩。

## 数据结构

每轮：

```json
{
  "question": "用户问题",
  "intent": "HOT_ARTICLE",
  "declaration": "我将查询：热门内容 TOP10",
  "sql": "SELECT ... LIMIT 10",
  "rowCount": 10,
  "conclusion": "一句话结论"
}
```

默认保留最近 6 轮。

## 压缩规则（超预算时按顺序执行）

1. 先裁剪工具结果：SQL 只保留行数，结论只保留一句话。
2. 再压缩：把最老的轮次合并成一段摘要，标注 `compressed=true`。
3. 压缩摘要不作为事实来源：摘要中如出现可跨会话复用的稳定事实，转交长期记忆沉淀器。

## 输出（JSON only）

```json
{
  "turns": [
    {"question": "...", "intent": "HOT_ARTICLE", "declaration": "...", "rowCount": 10, "conclusion": "..."}
  ],
  "compressed": true,
  "compressedSummary": "更早轮次的一句话摘要"
}
```

## 约束

- 短期记忆只服务指代理解（「刚才那 3 篇」），不充当本次查询的事实来源。
- 预算上限（≤ 800 tokens）超限时必须压缩，禁止静默丢弃全部轮次。
