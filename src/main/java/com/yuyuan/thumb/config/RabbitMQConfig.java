package com.yuyuan.thumb.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.module.SimpleModule;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.yuyuan.thumb.monitor.RabbitErrorHandler;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.config.SimpleRabbitListenerContainerFactory;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * RabbitMQ配置类
 */
@Configuration
@Slf4j
public class RabbitMQConfig {

    // 交换机名称
    public static final String THUMB_EXCHANGE = "thumb.exchange";
    
    // 队列名称
    public static final String THUMB_QUEUE = "thumb.queue";
    
    // 死信交换机
    public static final String THUMB_DLX_EXCHANGE = "thumb.dlx.exchange";
    
    // 死信队列
    public static final String THUMB_DLQ_QUEUE = "thumb.dlq.queue";
    
    // 路由键
    public static final String THUMB_ROUTING_KEY = "thumb.routing.key";
    public static final String THUMB_DLQ_ROUTING_KEY = "thumb.dlq.routing.key";
    @Bean
    public ObjectMapper objectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.registerModule(new JavaTimeModule());
        SimpleModule longToStringModule = new SimpleModule();
        longToStringModule.addSerializer(Long.class, ToStringSerializer.instance);
        longToStringModule.addSerializer(Long.TYPE, ToStringSerializer.instance);
        mapper.registerModule(longToStringModule);
        mapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS); // 输出 "2024-07-10T10:00:00" 而非时间戳数组
        return mapper;
    }
    /**
     * 消息转换器 - 使用JSON序列化
     */
    @Bean
    public MessageConverter jsonMessageConverter(ObjectMapper objectMapper) {
        return new Jackson2JsonMessageConverter(objectMapper);
    }
    /**
     * RabbitTemplate配置
     */
    @Bean
    public RabbitTemplate rabbitTemplate(ConnectionFactory connectionFactory,ObjectMapper objectMapper) {
        RabbitTemplate rabbitTemplate = new RabbitTemplate(connectionFactory);
        rabbitTemplate.setMessageConverter(jsonMessageConverter(objectMapper));
        // Unroutable events are returned by the broker instead of being silently dropped.
        rabbitTemplate.setMandatory(true);
        rabbitTemplate.setConfirmCallback((correlationData, ack, cause) -> {
            if (!ack) {
                log.warn("RabbitMQ publish NACK: correlation={}, cause={}", correlationData, cause);
            }
        });
        rabbitTemplate.setReturnsCallback(returned ->
                log.warn("RabbitMQ message unroutable: exchange={}, routingKey={}, replyText={}",
                        returned.getExchange(), returned.getRoutingKey(), returned.getReplyText()));
        return rabbitTemplate;
    }

    /**
     * 监听器容器工厂配置
     */
    @Bean
    public SimpleRabbitListenerContainerFactory rabbitListenerContainerFactory(ConnectionFactory connectionFactory,ObjectMapper objectMapper, RabbitErrorHandler rabbitErrorHandler) {
        SimpleRabbitListenerContainerFactory factory = new SimpleRabbitListenerContainerFactory();
        factory.setConnectionFactory(connectionFactory);
        factory.setMessageConverter(jsonMessageConverter(objectMapper));
        factory.setConcurrentConsumers(3);
        factory.setMaxConcurrentConsumers(10);
        factory.setPrefetchCount(100);
        factory.setAcknowledgeMode(AcknowledgeMode.MANUAL);
        factory.setErrorHandler(rabbitErrorHandler);
        return factory;
    }

    /**
     * 点赞交换机
     */
    @Bean
    public DirectExchange thumbExchange() {
        return new DirectExchange(THUMB_EXCHANGE, true, false);
    }

    /**
     * 点赞队列 - 配置死信交换机
     */
    @Bean
    public Queue thumbQueue() {
        return QueueBuilder.durable(THUMB_QUEUE)
                .withArgument("x-dead-letter-exchange", THUMB_DLX_EXCHANGE)
                .withArgument("x-dead-letter-routing-key", THUMB_DLQ_ROUTING_KEY)
                .build();
    }

    /**
     * 绑定点赞队列到交换机
     */
    @Bean
    public Binding thumbBinding() {
        return BindingBuilder.bind(thumbQueue()).to(thumbExchange()).with(THUMB_ROUTING_KEY);
    }

    /**
     * 死信交换机
     */
    @Bean
    public DirectExchange thumbDlxExchange() {
        return new DirectExchange(THUMB_DLX_EXCHANGE, true, false);
    }

    /**
     * 死信队列
     */
    @Bean
    public Queue thumbDlqQueue() {
        return QueueBuilder.durable(THUMB_DLQ_QUEUE).build();
    }

    /**
     * 绑定死信队列到死信交换机
     */
    @Bean
    public Binding thumbDlqBinding() {
        return BindingBuilder.bind(thumbDlqQueue()).to(thumbDlxExchange()).with(THUMB_DLQ_ROUTING_KEY);
    }
}
