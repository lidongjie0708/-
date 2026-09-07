package com.yuyuan.thumb.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuyuan.thumb.mapper.OutboxEventMapper;
import com.yuyuan.thumb.metrics.OutboxMetrics;
import com.yuyuan.thumb.model.entity.OutboxEvent;
import com.yuyuan.thumb.service.OutboxEventService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class OutboxEventServiceImpl extends ServiceImpl<OutboxEventMapper, OutboxEvent>
        implements OutboxEventService {

    private static final int MAX_RETRY_COUNT = 8;

    private final ObjectMapper objectMapper;
    private final OutboxMetrics outboxMetrics;

    @Override
    public void create(String eventType, String aggregateType, String aggregateId,
                       String exchangeName, String routingKey, Object payload) {
        OutboxEvent event = new OutboxEvent();
        event.setEventType(eventType);
        event.setAggregateType(aggregateType);
        event.setAggregateId(aggregateId);
        event.setExchangeName(exchangeName);
        event.setRoutingKey(routingKey);
        event.setPayload(writePayload(payload));
        event.setStatus("NEW");
        event.setRetryCount(0);
        event.setNextRetryTime(LocalDateTime.now());
        save(event);
        outboxMetrics.recordCreated(eventType);
    }

    @Override
    public List<OutboxEvent> listReadyEvents(int limit) {
        return list(new LambdaQueryWrapper<OutboxEvent>()
                .in(OutboxEvent::getStatus, "NEW", "FAILED")
                .le(OutboxEvent::getNextRetryTime, LocalDateTime.now())
                .orderByAsc(OutboxEvent::getCreatedAt)
                .last("LIMIT " + Math.max(1, limit)));
    }

    @Override
    public boolean markSending(Long id) {
        return update(new LambdaUpdateWrapper<OutboxEvent>()
                .eq(OutboxEvent::getId, id)
                .in(OutboxEvent::getStatus, "NEW", "FAILED")
                .set(OutboxEvent::getStatus, "SENDING")
                .set(OutboxEvent::getUpdatedAt, LocalDateTime.now()));
    }

    @Override
    public void markSent(Long id) {
        update(new LambdaUpdateWrapper<OutboxEvent>()
                .eq(OutboxEvent::getId, id)
                .set(OutboxEvent::getStatus, "SENT")
                .set(OutboxEvent::getLastError, null)
                .set(OutboxEvent::getUpdatedAt, LocalDateTime.now()));
    }

    @Override
    public void markFailed(Long id, String errorMessage) {
        OutboxEvent event = getById(id);
        int retryCount = event == null || event.getRetryCount() == null ? 1 : event.getRetryCount() + 1;
        String nextStatus = retryCount >= MAX_RETRY_COUNT ? "DEAD" : "FAILED";
        outboxMetrics.recordRetry(retryCount);
        if ("DEAD".equals(nextStatus) && event != null) {
            outboxMetrics.recordDead(event.getEventType());
        }
        update(new LambdaUpdateWrapper<OutboxEvent>()
                .eq(OutboxEvent::getId, id)
                .set(OutboxEvent::getStatus, nextStatus)
                .set(OutboxEvent::getRetryCount, retryCount)
                .set(OutboxEvent::getNextRetryTime, LocalDateTime.now().plusSeconds(backoffSeconds(retryCount)))
                .set(OutboxEvent::getLastError, truncate(errorMessage))
                .set(OutboxEvent::getUpdatedAt, LocalDateTime.now()));
    }

    private String writePayload(Object payload) {
        try {
            return objectMapper.writeValueAsString(payload);
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("Outbox payload serialize failed", e);
        }
    }

    private long backoffSeconds(int retryCount) {
        return Math.min(300L, (long) Math.pow(2, Math.min(retryCount, 8)));
    }

    private String truncate(String message) {
        if (message == null) {
            return null;
        }
        return message.length() > 1000 ? message.substring(0, 1000) : message;
    }
}
