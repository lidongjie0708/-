package com.yuyuan.thumb.listener.agent.msg;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 评论 Agent 异步处理事件
 * <p>
 * 评论创建后，发送此事件到 RabbitMQ，由消费者异步调用 Agent 做审核和情感分析
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CommentAgentEvent {
    /** 评论 ID */
    private Long commentId;
    /** 博客 ID */
    private String blogId;
    /** 用户 ID */
    private Long userId;
    /** 事件时间 */
    private LocalDateTime eventTime;
}