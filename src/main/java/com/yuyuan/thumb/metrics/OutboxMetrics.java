package com.yuyuan.thumb.metrics;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.yuyuan.thumb.mapper.OutboxEventMapper;
import com.yuyuan.thumb.model.entity.OutboxEvent;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Micrometer metrics for the outbox publication path.
 *
 * <p>Pending/age gauges are refreshed on a schedule; Prometheus scrapes never
 * trigger database queries, mirroring {@code RabbitQueueMetrics}.</p>
 */
@Component
public class OutboxMetrics {

    private static final List<String> EVENT_TYPES = List.of("THUMB_STATE", "BLOG_AGENT");
    private static final List<String> PENDING_STATUSES = List.of("NEW", "FAILED", "DEAD");

    private final MeterRegistry meterRegistry;
    private final OutboxEventMapper outboxEventMapper;
    private final Map<String, AtomicLong> pendingGauges = new ConcurrentHashMap<>();
    private final AtomicLong oldestPendingAgeSeconds = new AtomicLong();
    private final Counter pollFailures;

    public OutboxMetrics(MeterRegistry meterRegistry, OutboxEventMapper outboxEventMapper) {
        this.meterRegistry = meterRegistry;
        this.outboxEventMapper = outboxEventMapper;
        for (String eventType : EVENT_TYPES) {
            for (String status : PENDING_STATUSES) {
                AtomicLong value = new AtomicLong();
                pendingGauges.put(key(eventType, status), value);
                Gauge.builder("thumb.outbox.pending", value, AtomicLong::get)
                        .description("Outbox events awaiting broker publication")
                        .tags("event_type", eventType, "status", status)
                        .register(meterRegistry);
            }
        }
        Gauge.builder("thumb.outbox.age", oldestPendingAgeSeconds, AtomicLong::get)
                .description("Age in seconds of the oldest NEW/FAILED outbox event")
                .register(meterRegistry);
        this.pollFailures = Counter.builder("thumb.outbox.poll.failures")
                .description("Failed outbox pending-metrics refresh attempts")
                .register(meterRegistry);
    }

    public void recordCreated(String eventType) {
        meterRegistry.counter("thumb.outbox.created.total", "event_type", eventType).increment();
    }

    public void recordPublished(String eventType) {
        meterRegistry.counter("thumb.outbox.published.total", "event_type", eventType, "result", "success").increment();
    }

    public void recordPublishFailed(String eventType) {
        meterRegistry.counter("thumb.outbox.published.total", "event_type", eventType, "result", "failed").increment();
    }

    public void recordPublishLatency(String eventType, Duration duration) {
        meterRegistry.timer("thumb.outbox.publish.latency", "event_type", eventType).record(duration);
    }

    public void recordRetry(int retryCount) {
        meterRegistry.summary("thumb.outbox.retries").record(retryCount);
    }

    public void recordDead(String eventType) {
        meterRegistry.counter("thumb.outbox.dead.total", "event_type", eventType).increment();
    }

    @Scheduled(fixedDelayString = "${monitoring.outbox.refresh-ms:5000}")
    public void refreshPending() {
        try {
            Map<String, Long> counts = countPendingByEventTypeAndStatus();
            for (String eventType : EVENT_TYPES) {
                for (String status : PENDING_STATUSES) {
                    pendingGauges.get(key(eventType, status)).set(
                            counts.getOrDefault(key(eventType, status), 0L));
                }
            }
            oldestPendingAgeSeconds.set(oldestPendingAgeSeconds());
        } catch (Exception exception) {
            pollFailures.increment();
        }
    }

    private Map<String, Long> countPendingByEventTypeAndStatus() {
        Map<String, Long> counts = new ConcurrentHashMap<>();
        List<Map<String, Object>> rows = outboxEventMapper.selectMaps(new QueryWrapper<OutboxEvent>()
                .select("event_type AS event_type, status AS status, COUNT(*) AS cnt")
                .in("status", PENDING_STATUSES)
                .groupBy("event_type", "status"));
        for (Map<String, Object> row : rows) {
            counts.put(key(String.valueOf(row.get("event_type")), String.valueOf(row.get("status"))),
                    ((Number) row.get("cnt")).longValue());
        }
        return counts;
    }

    private long oldestPendingAgeSeconds() {
        List<Object> values = outboxEventMapper.selectObjs(new QueryWrapper<OutboxEvent>()
                .select("MIN(TIMESTAMPDIFF(SECOND, created_at, NOW())) AS age")
                .in("status", "NEW", "FAILED"));
        if (values == null || values.isEmpty() || values.get(0) == null) {
            return 0;
        }
        return ((Number) values.get(0)).longValue();
    }

    private String key(String eventType, String status) {
        return eventType + ":" + status;
    }
}
