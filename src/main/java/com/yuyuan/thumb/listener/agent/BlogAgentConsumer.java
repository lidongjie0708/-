package com.yuyuan.thumb.listener.agent;

import com.rabbitmq.client.Channel;
import com.yuyuan.thumb.config.RabbitMQAgentConfig;
import com.yuyuan.thumb.listener.agent.msg.BlogAgentEvent;
import com.yuyuan.thumb.model.entity.Blog;
import com.yuyuan.thumb.service.BlogService;
import com.yuyuan.thumb.service.agent.AgentService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Service;

import java.io.IOException;

/**
 * 博客 Agent 消费者
 * <p>
 * 消费 RabbitMQ 中的博客事件，异步调用 Agent 服务生成摘要、推荐标签、向量化
 */
@Service
@Slf4j
public class BlogAgentConsumer {

    private final BlogService blogService;
    private final AgentService agentService;

    public BlogAgentConsumer(BlogService blogService, AgentService agentService) {
        this.blogService = blogService;
        this.agentService = agentService;
    }

    /**
     * 处理博客 Agent 事件
     */
    @RabbitListener(queues = RabbitMQAgentConfig.BLOG_AGENT_QUEUE,
            containerFactory = "rabbitListenerContainerFactory")
    public void consumeBlogEvent(BlogAgentEvent event, Message message, Channel channel) throws IOException {
        try {
            log.info("收到博客 Agent 事件: blogId={}, action={}", event.getBlogId(), event.getActionType());

            Blog blog = blogService.getById(event.getBlogId());
            if (blog == null) {
                log.warn("博客不存在，跳过处理: blogId={}", event.getBlogId());
                channel.basicAck(message.getMessageProperties().getDeliveryTag(), false);
                return;
            }

            // 同步调用 Agent 处理
            agentService.processBlogSync(blog);

            channel.basicAck(message.getMessageProperties().getDeliveryTag(), false);
            log.info("博客 Agent 处理完成: blogId={}", event.getBlogId());

        } catch (Exception e) {
            log.error("处理博客 Agent 事件失败: blogId={}", event.getBlogId(), e);
            // 拒绝消息，进入死信队列
            channel.basicNack(message.getMessageProperties().getDeliveryTag(), false, false);
        }
    }
}