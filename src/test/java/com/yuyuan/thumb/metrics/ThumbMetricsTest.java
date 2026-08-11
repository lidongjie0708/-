package com.yuyuan.thumb.metrics;

import io.micrometer.core.instrument.Timer;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ThumbMetricsTest {

    private final SimpleMeterRegistry registry = new SimpleMeterRegistry();
    private final ThumbMetrics metrics = new ThumbMetrics(registry);

    @Test
    void countsIdempotentRejectsPerOperation() {
        metrics.recordIdempotentReject("do");
        metrics.recordIdempotentReject("do");
        metrics.recordIdempotentReject("undo");

        assertEquals(2D, registry.get("thumb.idempotent.reject.total").tag("operation", "do").counter().count());
        assertEquals(1D, registry.get("thumb.idempotent.reject.total").tag("operation", "undo").counter().count());
    }

    @Test
    void countsProjectionDeltasByActionAndResult() {
        metrics.recordProjectionDelta("insert", true);
        metrics.recordProjectionDelta("insert", false);
        metrics.recordProjectionDelta("delete", true);

        assertEquals(1D, registry.get("thumb.consumer.projection.delta.total")
                .tags("action", "insert", "result", "applied").counter().count());
        assertEquals(1D, registry.get("thumb.consumer.projection.delta.total")
                .tags("action", "insert", "result", "skipped").counter().count());
        assertEquals(1D, registry.get("thumb.consumer.projection.delta.total")
                .tags("action", "delete", "result", "applied").counter().count());
    }

    @Test
    void countsConsumerNackAndDlqIngress() {
        metrics.recordConsumerNack();
        metrics.recordConsumerNack();
        metrics.recordDlqIngress();

        assertEquals(2D, registry.get("thumb.consumer.nack.total").counter().count());
        assertEquals(1D, registry.get("thumb.rabbitmq.dlq.ingress.total").counter().count());
    }

    @Test
    void recordsProjectionLatency() {
        metrics.recordProjectionLatency(Duration.ofMillis(150));

        Timer timer = registry.get("thumb.consumer.projection.latency").timer();
        assertEquals(1L, timer.count());
        assertEquals(150_000_000D, timer.totalTime(TimeUnit.NANOSECONDS), 1_000_000D);
    }

    @Test
    void recordsReconciliationRepairsAndConsistencyGap() {
        metrics.recordReconciledRepairs(7);
        metrics.recordReconciledRepairs(3);
        metrics.setConsistencyGap(-5);

        assertEquals(10D, registry.get("thumb.reconcile.repaired.total").counter().count());
        assertEquals(-5D, registry.get("thumb.consistency.gap").gauge().value());
    }
}
