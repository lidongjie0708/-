package com.yuyuan.thumb.metrics;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.yuyuan.thumb.mapper.OutboxEventMapper;
import com.yuyuan.thumb.model.entity.OutboxEvent;
import io.micrometer.core.instrument.Timer;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.time.Duration;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

class OutboxMetricsTest {

    private final SimpleMeterRegistry registry = new SimpleMeterRegistry();
    private final OutboxEventMapper outboxEventMapper = Mockito.mock(OutboxEventMapper.class);
    private final OutboxMetrics metrics = new OutboxMetrics(registry, outboxEventMapper);

    @Test
    void countsCreatedAndPublishedPerEventType() {
        metrics.recordCreated("THUMB_STATE");
        metrics.recordCreated("THUMB_STATE");
        metrics.recordPublished("THUMB_STATE");
        metrics.recordPublishFailed("BLOG_AGENT");

        assertEquals(2D, registry.get("thumb.outbox.created.total").tag("event_type", "THUMB_STATE").counter().count());
        assertEquals(1D, registry.get("thumb.outbox.published.total")
                .tags("event_type", "THUMB_STATE", "result", "success").counter().count());
        assertEquals(1D, registry.get("thumb.outbox.published.total")
                .tags("event_type", "BLOG_AGENT", "result", "failed").counter().count());
    }

    @Test
    void recordsPublishLatencyRetriesAndDead() {
        metrics.recordPublishLatency("THUMB_STATE", Duration.ofMillis(200));
        metrics.recordRetry(3);
        metrics.recordDead("THUMB_STATE");

        Timer timer = registry.get("thumb.outbox.publish.latency").tag("event_type", "THUMB_STATE").timer();
        assertEquals(1L, timer.count());
        assertEquals(1L, registry.get("thumb.outbox.retries").summary().count());
        assertEquals(1D, registry.get("thumb.outbox.dead.total").tag("event_type", "THUMB_STATE").counter().count());
    }

    @Test
    void refreshPendingComputesGaugesFromDatabase() {
        when(outboxEventMapper.selectMaps(any(QueryWrapper.class))).thenReturn(List.of(
                Map.of("event_type", "THUMB_STATE", "status", "NEW", "cnt", 3L),
                Map.of("event_type", "THUMB_STATE", "status", "FAILED", "cnt", 1L)
        ));
        when(outboxEventMapper.selectObjs(any(QueryWrapper.class))).thenReturn(List.of(42L));

        metrics.refreshPending();

        assertEquals(3D, registry.get("thumb.outbox.pending")
                .tags("event_type", "THUMB_STATE", "status", "NEW").gauge().value());
        assertEquals(1D, registry.get("thumb.outbox.pending")
                .tags("event_type", "THUMB_STATE", "status", "FAILED").gauge().value());
        assertEquals(0D, registry.get("thumb.outbox.pending")
                .tags("event_type", "THUMB_STATE", "status", "DEAD").gauge().value());
        assertEquals(42D, registry.get("thumb.outbox.age").gauge().value());
    }
}
