package com.yuyuan.thumb.metrics;

import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Exposes the most recent completed Redis/MySQL thumb reconciliation result.
 *
 * <p>The gauges are backed by in-memory values only. Prometheus scrapes never trigger Redis or MySQL reads.</p>
 */
@Component
public class ThumbReconciliationMetrics {

    private final AtomicLong redisOnlyPairs = new AtomicLong();
    private final AtomicLong mysqlOnlyPairs = new AtomicLong();
    private final AtomicLong scannedRedisPairs = new AtomicLong();
    private final AtomicLong scannedMysqlPairs = new AtomicLong();
    private final AtomicLong lastSuccessEpochSeconds = new AtomicLong();
    private final AtomicLong snapshotComplete = new AtomicLong();

    public ThumbReconciliationMetrics(MeterRegistry meterRegistry) {
        Gauge.builder("thumb.reconciliation.difference.pairs", redisOnlyPairs, AtomicLong::get)
                .description("Redis/MySQL thumb state differences from the last completed reconciliation")
                .tag("direction", "redis_only")
                .register(meterRegistry);
        Gauge.builder("thumb.reconciliation.difference.pairs", mysqlOnlyPairs, AtomicLong::get)
                .description("Redis/MySQL thumb state differences from the last completed reconciliation")
                .tag("direction", "mysql_only")
                .register(meterRegistry);
        Gauge.builder("thumb.reconciliation.scanned.pairs", scannedRedisPairs, AtomicLong::get)
                .description("Redis thumb pairs scanned by the last reconciliation")
                .tag("store", "redis")
                .register(meterRegistry);
        Gauge.builder("thumb.reconciliation.scanned.pairs", scannedMysqlPairs, AtomicLong::get)
                .description("MySQL thumb pairs scanned by the last reconciliation")
                .tag("store", "mysql")
                .register(meterRegistry);
        Gauge.builder("thumb.reconciliation.last.success", lastSuccessEpochSeconds, AtomicLong::get)
                .description("Unix timestamp of the last complete thumb reconciliation")
                .register(meterRegistry);
        Gauge.builder("thumb.reconciliation.snapshot.complete", snapshotComplete, AtomicLong::get)
                .description("Whether the latest reconciliation scanned the complete configured data set (1=true, 0=false)")
                .register(meterRegistry);
    }

    public void recordComplete(long redisOnly, long mysqlOnly, long redisScanned, long mysqlScanned) {
        redisOnlyPairs.set(redisOnly);
        mysqlOnlyPairs.set(mysqlOnly);
        scannedRedisPairs.set(redisScanned);
        scannedMysqlPairs.set(mysqlScanned);
        lastSuccessEpochSeconds.set(Instant.now().getEpochSecond());
        snapshotComplete.set(1);
    }

    public void recordIncomplete(long redisScanned, long mysqlScanned) {
        scannedRedisPairs.set(redisScanned);
        scannedMysqlPairs.set(mysqlScanned);
        snapshotComplete.set(0);
    }
}
