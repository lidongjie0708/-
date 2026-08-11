package com.yuyuan.thumb.monitor;

import com.yuyuan.thumb.config.RabbitMQConfig;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tags;
import org.springframework.amqp.core.AmqpAdmin;
import org.springframework.amqp.core.QueueInformation;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Periodically samples the queues that make up the asynchronous thumb write path.
 *
 * <p>Using gauges instead of an HTTP call at scrape time keeps Prometheus scraping
 * inexpensive and makes a broker outage visible through {@code poll_failures_total}.
 * The message count includes ready and unacknowledged messages, so it represents the
 * work still outstanding for eventual consistency.</p>
 */
@Component
public class RabbitQueueMetrics {

    private static final List<String> QUEUES = List.of(
            RabbitMQConfig.THUMB_QUEUE,
            RabbitMQConfig.THUMB_DLQ_QUEUE
    );

    private final AmqpAdmin amqpAdmin;
    private final Map<String, AtomicLong> messageCounts = new ConcurrentHashMap<>();
    private final Map<String, AtomicLong> consumerCounts = new ConcurrentHashMap<>();
    private final Counter pollFailures;

    public RabbitQueueMetrics(AmqpAdmin amqpAdmin, MeterRegistry meterRegistry) {
        this.amqpAdmin = amqpAdmin;
        this.pollFailures = Counter.builder("thumb.rabbitmq.queue.poll.failures")
                .description("Failed RabbitMQ queue metric polling attempts")
                .register(meterRegistry);
        for (String queue : QUEUES) {
            AtomicLong messages = new AtomicLong();
            AtomicLong consumers = new AtomicLong();
            messageCounts.put(queue, messages);
            consumerCounts.put(queue, consumers);
            Tags tags = Tags.of("queue", queue);
            meterRegistry.gauge("thumb.rabbitmq.queue.messages", tags, messages);
            meterRegistry.gauge("thumb.rabbitmq.queue.consumers", tags, consumers);
        }
    }

    @PostConstruct
    public void initialize() {
        refresh();
    }

    @Scheduled(fixedDelayString = "${monitoring.rabbitmq.queue-refresh-ms:5000}")
    public void refresh() {
        for (String queue : QUEUES) {
            try {
                QueueInformation information = amqpAdmin.getQueueInfo(queue);
                if (information == null) {
                    messageCounts.get(queue).set(0);
                    consumerCounts.get(queue).set(0);
                    continue;
                }
                messageCounts.get(queue).set(information.getMessageCount());
                consumerCounts.get(queue).set(information.getConsumerCount());
            } catch (Exception exception) {
                pollFailures.increment();
            }
        }
    }
}
