package com.yuyuan.thumb.listener.agent.msg;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 博客 Agent 异步处理事件
 * <p>
 * 博客创建/更新后，发送此事件到 RabbitMQ，由消费者异步调用 Agent 处理
 * 避免阻塞主线程响应时间
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class BlogAgentEvent {
    /** 博客 ID */
    private Long blogId;
    /** 用户 ID */
    private Long userId;
    /** 操作类型：CREATE/UPDATE */
    private ActionType actionType;
    /** 事件时间 */
    private LocalDateTime eventTime;

    public enum ActionType {
        CREATE,
        UPDATE
    }
}