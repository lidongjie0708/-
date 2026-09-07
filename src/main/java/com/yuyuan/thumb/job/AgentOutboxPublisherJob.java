package com.yuyuan.thumb.job;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuyuan.thumb.listener.agent.msg.BlogAgentEvent;
import com.yuyuan.thumb.listener.thumb.msg.ThumbEvent;
import com.yuyuan.thumb.metrics.OutboxMetrics;
import com.yuyuan.thumb.model.entity.OutboxEvent;
import com.yuyuan.thumb.service.OutboxEventService;
import com.google.common.util.concurrent.ThreadFactoryBuilder;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
@RequiredArgsConstructor
public class AgentOutboxPublisherJob {

    private final OutboxEventService outboxEventService;
    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;
    private final OutboxMetrics outboxMetrics;

    @Value("${thumb.outbox.batch-size:200}")
    private int batchSize;

    @Value("${thumb.outbox.parallelism:4}")
    private int parallelism;

    private ExecutorService publisherExecutor;

    @PostConstruct
    public void init() {
        publisherExecutor = Executors.newFixedThreadPool(Math.max(1, parallelism),
                new ThreadFactoryBuilder().setNameFormat("outbox-publisher-%d").build());
    }

    @PreDestroy
    public void shutdown() {
        if (publisherExecutor != null) {
            publisherExecutor.shutdown();
        }
    }

    @Scheduled(fixedDelayString = "${thumb.outbox.publish-interval-ms:1000}")
    public void publishReadyEvents() {
        List<OutboxEvent> events = outboxEventService.listReadyEvents(Math.max(1, batchSize));
        if (events.isEmpty()) {
            return;
        }
        List<CompletableFuture<Void>> futures = events.stream()
                .map(event -> CompletableFuture.runAsync(() -> publishOne(event), publisherExecutor))
                .toList();
        for (CompletableFuture<Void> future : futures) {
            try {
                future.get(10, TimeUnit.SECONDS);
            } catch (Exception e) {
                log.warn("Outbox publish task did not complete in time: {}", e.getMessage());
            }
        }
    }

    private void publishOne(OutboxEvent event) {
        if (!outboxEventService.markSending(event.getId())) {
            return;
        }
        try {
            Object payload = resolvePayload(event);
            CorrelationData correlationData = new CorrelationData(String.valueOf(event.getId()));
            rabbitTemplate.convertAndSend(event.getExchangeName(), event.getRoutingKey(), payload, correlationData);
            CorrelationData.Confirm confirm = correlationData.getFuture().get(5, TimeUnit.SECONDS);
            if (confirm == null || !confirm.isAck()) {
                throw new IllegalStateException("Broker did not confirm event: "
                        + (confirm == null ? "timeout" : confirm.getReason()));
            }
            outboxEventService.markSent(event.getId());
            outboxMetrics.recordPublished(event.getEventType());
            if (event.getCreatedAt() != null) {
                outboxMetrics.recordPublishLatency(event.getEventType(),
                        Duration.between(event.getCreatedAt(), LocalDateTime.now()));
            }
            log.info("Outbox event published: id={}, type={}, aggregateId={}",
                    event.getId(), event.getEventType(), event.getAggregateId());
        } catch (Exception e) {
            outboxEventService.markFailed(event.getId(), e.getMessage());
            outboxMetrics.recordPublishFailed(event.getEventType());
            log.error("Outbox event publish failed: id={}, type={}", event.getId(), event.getEventType(), e);
        }
    }

    private Object resolvePayload(OutboxEvent event) throws Exception {
        if ("BLOG_AGENT".equals(event.getEventType())) {
            return objectMapper.readValue(event.getPayload(), BlogAgentEvent.class);
        }
        if ("THUMB_STATE".equals(event.getEventType())) {
            return objectMapper.readValue(event.getPayload(), ThumbEvent.class);
        }
        return event.getPayload();
    }
}
