package com.yuyuan.thumb.job;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuyuan.thumb.listener.agent.msg.BlogAgentEvent;
import com.yuyuan.thumb.model.entity.OutboxEvent;
import com.yuyuan.thumb.service.OutboxEventService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class AgentOutboxPublisherJob {

    private final OutboxEventService outboxEventService;
    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;

    @Scheduled(fixedDelay = 3000)
    public void publishReadyEvents() {
        for (OutboxEvent event : outboxEventService.listReadyEvents(50)) {
            if (!outboxEventService.markSending(event.getId())) {
                continue;
            }
            try {
                Object payload = resolvePayload(event);
                rabbitTemplate.convertAndSend(event.getExchangeName(), event.getRoutingKey(), payload);
                outboxEventService.markSent(event.getId());
                log.info("Outbox event published: id={}, type={}, aggregateId={}",
                        event.getId(), event.getEventType(), event.getAggregateId());
            } catch (Exception e) {
                outboxEventService.markFailed(event.getId(), e.getMessage());
                log.error("Outbox event publish failed: id={}, type={}", event.getId(), event.getEventType(), e);
            }
        }
    }

    private Object resolvePayload(OutboxEvent event) throws Exception {
        if ("BLOG_AGENT".equals(event.getEventType())) {
            return objectMapper.readValue(event.getPayload(), BlogAgentEvent.class);
        }
        return event.getPayload();
    }
}
