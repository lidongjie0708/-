package com.yuyuan.thumb.model.dto.agent;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.HashMap;
import java.util.Map;

/**
 * 发送给 Python Agent 服务的请求体
 * <p>
 * 支持多种 Agent 任务类型，通过 action 字段路由。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AgentRequest {

    /** 任务类型：summary-摘要, tags-标签, embed-向量化, audit-comment-评论审核 */
    private String action;

    /** 内容文本（博客内容 / 评论内容） */
    private String content;

    /** 内容标题（博客摘要/标签任务需要） */
    private String title;

    /** 内容 ID（博客 ID / 评论 ID） */
    private String contentId;

    /** 额外参数的扩展字段 */
    @Builder.Default
    private Map<String, Object> extra = new HashMap<>();
}
