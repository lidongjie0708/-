package com.yuyuan.thumb.monitor;

import com.yuyuan.thumb.config.RabbitMQConfig;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.AmqpAdmin;
import org.springframework.amqp.core.QueueInformation;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class RabbitQueueMetricsTest {

    @Test
    void refreshPublishesBrokerBacklogAndConsumerCounts() {
        AmqpAdmin amqpAdmin = mock(AmqpAdmin.class);
        QueueInformation thumbQueue = mock(QueueInformation.class);
        QueueInformation deadLetterQueue = mock(QueueInformation.class);
        when(thumbQueue.getMessageCount()).thenReturn(17);
        when(thumbQueue.getConsumerCount()).thenReturn(3);
        when(deadLetterQueue.getMessageCount()).thenReturn(2);
        when(deadLetterQueue.getConsumerCount()).thenReturn(1);
        when(amqpAdmin.getQueueInfo(RabbitMQConfig.THUMB_QUEUE)).thenReturn(thumbQueue);
        when(amqpAdmin.getQueueInfo(RabbitMQConfig.THUMB_DLQ_QUEUE)).thenReturn(deadLetterQueue);

        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        RabbitQueueMetrics metrics = new RabbitQueueMetrics(amqpAdmin, registry);
        metrics.refresh();

        assertThat(registry.get("thumb.rabbitmq.queue.messages")
                .tag("queue", RabbitMQConfig.THUMB_QUEUE).gauge().value()).isEqualTo(17.0);
        assertThat(registry.get("thumb.rabbitmq.queue.consumers")
                .tag("queue", RabbitMQConfig.THUMB_QUEUE).gauge().value()).isEqualTo(3.0);
        assertThat(registry.get("thumb.rabbitmq.queue.messages")
                .tag("queue", RabbitMQConfig.THUMB_DLQ_QUEUE).gauge().value()).isEqualTo(2.0);
    }
}
