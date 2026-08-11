package com.yuyuan.thumb.monitor;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.listener.ConditionalRejectingErrorHandler;
import org.springframework.amqp.support.converter.MessageConversionException;
import org.springframework.stereotype.Component;
import org.springframework.util.ErrorHandler;

/**
 * Container-level RabbitMQ error handler that counts messages rejected before
 * listener invocation (for example, unreadable payloads failing the message
 * converter). Those poison messages never reach the listener methods, so they
 * must be observed at the container boundary.
 */
@Slf4j
@Component
public class RabbitErrorHandler implements ErrorHandler {

    private final ConditionalRejectingErrorHandler delegate = new ConditionalRejectingErrorHandler();
    private final Counter conversionFailures;

    public RabbitErrorHandler(MeterRegistry meterRegistry) {
        this.conversionFailures = Counter.builder("thumb.rabbitmq.conversion.failures.total")
                .description("Messages rejected by the RabbitMQ message converter before listener invocation")
                .register(meterRegistry);
    }

    @Override
    public void handleError(Throwable t) {
        if (containsConversionFailure(t)) {
            conversionFailures.increment();
        }
        delegate.handleError(t);
    }

    private boolean containsConversionFailure(Throwable t) {
        Throwable cursor = t;
        while (cursor != null) {
            if (cursor instanceof MessageConversionException) {
                return true;
            }
            cursor = cursor.getCause();
        }
        return false;
    }
}
