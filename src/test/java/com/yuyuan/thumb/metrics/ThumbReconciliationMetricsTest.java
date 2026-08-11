package com.yuyuan.thumb.metrics;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ThumbReconciliationMetricsTest {

    @Test
    void publishesTheLastCompleteSnapshotAndMarksIncompleteAttempts() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        ThumbReconciliationMetrics metrics = new ThumbReconciliationMetrics(registry);

        metrics.recordComplete(3, 2, 10, 11);

        assertEquals(3D, registry.get("thumb.reconciliation.difference.pairs").tag("direction", "redis_only").gauge().value());
        assertEquals(2D, registry.get("thumb.reconciliation.difference.pairs").tag("direction", "mysql_only").gauge().value());
        assertEquals(1D, registry.get("thumb.reconciliation.snapshot.complete").gauge().value());

        metrics.recordIncomplete(12, 100_000);

        assertEquals(3D, registry.get("thumb.reconciliation.difference.pairs").tag("direction", "redis_only").gauge().value());
        assertEquals(0D, registry.get("thumb.reconciliation.snapshot.complete").gauge().value());
        assertEquals(12D, registry.get("thumb.reconciliation.scanned.pairs").tag("store", "redis").gauge().value());
    }
}
