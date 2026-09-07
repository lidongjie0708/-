# 长期记忆召回（Long-term Memory Retrieval）

## 任务

从候选长期记忆中选出与当前问题最相关的记忆，用于注入上下文（L1 层）。

## 输入

- 当前问题
- 候选记忆列表（含 content、importance、tags、scope）

## 选择规则

1. 相关性优先：与当前问题的主题、指标、维度有重叠的记忆优先。
2. 重要性门槛：importance ≥ 0.5 才考虑；重要性低于 0.5 不注入。
3. 数量上限：最多 5 条，总字符 ≤ 600。
4. 去重：同一事实只保留最新版本。
5. 权限：USER 级记忆只对本人可见，GLOBAL 级对所有管理员可见。

## 输出（JSON only）

```json
{
  "selected": [
    {
      "key": "user_123.preference.metric_scope",
      "content": "用户关注评论风险指标",
      "importance": 0.8
    }
  ]
}
```

## 约束

- 不修改、不合并记忆内容，只做选取。
- 没有相关记忆时输出 `{"selected": []}`，不要编造。
