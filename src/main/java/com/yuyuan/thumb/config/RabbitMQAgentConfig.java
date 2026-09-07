package com.yuyuan.thumb.config;

import org.springframework.amqp.core.*;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * RabbitMQ Agent 队列配置
 * <p>
 * 为 Agent 异步处理配置独立的交换机和队列，复用已有的死信机制
 */
@Configuration
public class RabbitMQAgentConfig {

    // Agent 交换机
    public static final String AGENT_EXCHANGE = "agent.exchange";

    // 博客 Agent 队列和路由键
    public static final String BLOG_AGENT_QUEUE = "agent.blog.queue";
    public static final String BLOG_AGENT_ROUTING_KEY = "agent.blog.routing.key";

    // 评论 Agent 队列和路由键
    public static final String COMMENT_AGENT_QUEUE = "agent.comment.queue";
    public static final String COMMENT_AGENT_ROUTING_KEY = "agent.comment.routing.key";

    /** Proposal events are auditable commands, not direct blog mutations. */
    public static final String OPERATION_ACTION_QUEUE = "agent.operation-action.queue";
    public static final String OPERATION_ACTION_ROUTING_KEY = "agent.operation-action.routing.key";

    // 死信交换机（复用原来点赞的死信配置）
    private static final String DLX_EXCHANGE = RabbitMQConfig.THUMB_DLX_EXCHANGE;
    private static final String DLX_ROUTING_KEY = RabbitMQConfig.THUMB_DLQ_ROUTING_KEY;

    /**
     * Agent 交换机
     */
    @Bean
    public DirectExchange agentExchange() {
        return new DirectExchange(AGENT_EXCHANGE, true, false);
    }

    /**
     * 博客 Agent 队列（配置死信）
     */
    @Bean
    public Queue blogAgentQueue() {
        return QueueBuilder.durable(BLOG_AGENT_QUEUE)
                .withArgument("x-dead-letter-exchange", DLX_EXCHANGE)
                .withArgument("x-dead-letter-routing-key", DLX_ROUTING_KEY)
                .build();
    }

    /**
     * 绑定博客 Agent 队列
     */
    @Bean
    public Binding blogAgentBinding() {
        return BindingBuilder.bind(blogAgentQueue()).to(agentExchange()).with(BLOG_AGENT_ROUTING_KEY);
    }

    /**
     * 评论 Agent 队列（配置死信）
     */
    @Bean
    public Queue commentAgentQueue() {
        return QueueBuilder.durable(COMMENT_AGENT_QUEUE)
                .withArgument("x-dead-letter-exchange", DLX_EXCHANGE)
                .withArgument("x-dead-letter-routing-key", DLX_ROUTING_KEY)
                .build();
    }

    /**
     * 绑定评论 Agent 队列
     */
    @Bean
    public Binding commentAgentBinding() {
        return BindingBuilder.bind(commentAgentQueue()).to(agentExchange()).with(COMMENT_AGENT_ROUTING_KEY);
    }

    @Bean
    public Queue operationActionQueue() {
        return QueueBuilder.durable(OPERATION_ACTION_QUEUE)
                .withArgument("x-dead-letter-exchange", DLX_EXCHANGE)
                .withArgument("x-dead-letter-routing-key", DLX_ROUTING_KEY)
                .build();
    }

    @Bean
    public Binding operationActionBinding() {
        return BindingBuilder.bind(operationActionQueue()).to(agentExchange()).with(OPERATION_ACTION_ROUTING_KEY);
    }
}
