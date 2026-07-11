package com.yuyuan.thumb.listener.agent;

import com.rabbitmq.client.Channel;
import com.yuyuan.thumb.config.RabbitMQAgentConfig;
import com.yuyuan.thumb.listener.agent.msg.CommentAgentEvent;
import com.yuyuan.thumb.model.entity.Comments;
import com.yuyuan.thumb.service.CommentService;
import com.yuyuan.thumb.service.agent.AgentService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Service;

import java.io.IOException;

/**
 * 评论 Agent 消费者
 * <p>
 * 消费 RabbitMQ 中的评论事件，异步调用 Agent 服务做审核和情感分析
 */
@Service
@Slf4j
public class CommentAgentConsumer {

    private final CommentService commentService;
    private final AgentService agentService;

    public CommentAgentConsumer(CommentService commentService, AgentService agentService) {
        this.commentService = commentService;
        this.agentService = agentService;
    }

    /**
     * 处理评论 Agent 事件
     */
    @RabbitListener(queues = RabbitMQAgentConfig.COMMENT_AGENT_QUEUE,
            containerFactory = "rabbitListenerContainerFactory")
    public void consumeCommentEvent(CommentAgentEvent event, Message message, Channel channel) throws IOException {
        try {
            log.info("收到评论 Agent 事件: commentId={}", event.getCommentId());

            Comments comment = commentService.getById(event.getCommentId());
            if (comment == null) {
                log.warn("评论不存在，跳过处理: commentId={}", event.getCommentId());
                channel.basicAck(message.getMessageProperties().getDeliveryTag(), false);
                return;
            }

            // 同步调用 Agent 处理
            agentService.processCommentSync(comment);

            channel.basicAck(message.getMessageProperties().getDeliveryTag(), false);
            log.info("评论 Agent 处理完成: commentId={}", event.getCommentId());

        } catch (Exception e) {
            log.error("处理评论 Agent 事件失败: commentId={}", event.getCommentId(), e);
            // 拒绝消息，进入死信队列
            channel.basicNack(message.getMessageProperties().getDeliveryTag(), false, false);
        }
    }
}