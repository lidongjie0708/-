package com.yuyuan.thumb.metrics;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Micrometer metrics for the thumb request -> Lua -> outbox -> RabbitMQ -> MySQL projection path.
 *
 * <p>Counters are registered lazily through {@link MeterRegistry#counter(String, String...)}
 * so dynamic tags (operation/action/result) stay cheap.</p>
 */
@Component
public class ThumbMetrics {

    private final MeterRegistry meterRegistry;
    private final AtomicLong consistencyGap = new AtomicLong();

    public ThumbMetrics(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
        Gauge.builder("thumb.consistency.gap", consistencyGap, AtomicLong::get)
                .description("Redis thumb-state pair count minus MySQL thumb row count from the last reconciliation")
                .register(meterRegistry);
    }

    /**
     * Lua script returned -1: duplicate thumb, or undo without a prior thumb.
     *
     * @param operation "do" or "undo"
     */
    public void recordIdempotentReject(String operation) {
        meterRegistry.counter("thumb.idempotent.reject.total", "operation", operation).increment();
    }

    /**
     * A projection changed MySQL state (insert/delete applied) or was skipped by idempotency.
     *
     * @param action  "insert" or "delete"
     * @param applied true when MySQL changed, false when skipped
     */
    public void recordProjectionDelta(String action, boolean applied) {
        meterRegistry.counter("thumb.consumer.projection.delta.total",
                "action", action,
                "result", applied ? "applied" : "skipped").increment();
    }

    /** A message was nacked and routed to the dead-letter queue. */
    public void recordConsumerNack() {
        meterRegistry.counter("thumb.consumer.nack.total").increment();
    }

    /** End-to-end time from event creation to successful MySQL projection. */
    public void recordProjectionLatency(Duration duration) {
        meterRegistry.timer("thumb.consumer.projection.latency").record(duration);
    }

    /** A message was consumed from the thumb dead-letter queue. */
    public void recordDlqIngress() {
        meterRegistry.counter("thumb.rabbitmq.dlq.ingress.total").increment();
    }

    /** Number of state pairs the reconciliation re-enqueued for repair. */
    public void recordReconciledRepairs(long count) {
        meterRegistry.counter("thumb.reconcile.repaired.total").increment(count);
    }

    /** Signed Redis-vs-MySQL difference observed by the last reconciliation. */
    public void setConsistencyGap(long gap) {
        consistencyGap.set(gap);
    }
}
