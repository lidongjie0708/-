package com.yuyuan.thumb.listener.thumb;

import com.baomidou.mybatisplus.core.toolkit.IdWorker;
import com.rabbitmq.client.Channel;
import com.yuyuan.thumb.config.RabbitMQConfig;
import com.yuyuan.thumb.listener.thumb.msg.ThumbEvent;
import com.yuyuan.thumb.mapper.ThumbMapper;
import com.yuyuan.thumb.metrics.ThumbMetrics;
import com.yuyuan.thumb.util.RedisKeyUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.io.IOException;
import java.time.Duration;
import java.time.LocalDateTime;

/** Projects Redis's current thumb state into MySQL. Events are triggers, not +/- commands. */
@Service
@Slf4j
@RequiredArgsConstructor
public class RabbitThumbConsumer {

    private final ThumbMapper thumbMapper;
    private final RedisTemplate<String, Object> redisTemplate;
    private final TransactionTemplate transactionTemplate;
    private final ThumbEventDecoder thumbEventDecoder;
    private final ThumbMetrics thumbMetrics;

    @RabbitListener(queues = RabbitMQConfig.THUMB_DLQ_QUEUE)
    public void consumeDlq(Message message, Channel channel) throws IOException {
        try {
            thumbMetrics.recordDlqIngress();
            ThumbEvent event = thumbEventDecoder.decode(message);
            log.error("Thumb event moved to DLQ: eventId={}, userId={}, blogId={}, xDeath={}",
                    event.getEventId(), event.getUserId(), event.getBlogId(),
                    message.getMessageProperties().getXDeathHeader());
        } catch (IllegalArgumentException exception) {
            // Acknowledge poison/legacy messages after recording metadata: the DLQ is terminal and must not loop.
            log.error("Unreadable thumb DLQ message acknowledged safely: deliveryTag={}, contentType={}, bodyBytes={}, xDeath={}",
                    message.getMessageProperties().getDeliveryTag(), message.getMessageProperties().getContentType(),
                    message.getBody().length, message.getMessageProperties().getXDeathHeader(), exception);
        }
        channel.basicAck(message.getMessageProperties().getDeliveryTag(), false);
    }

    @RabbitListener(queues = RabbitMQConfig.THUMB_QUEUE, containerFactory = "rabbitListenerContainerFactory")
    public void processThumbEvent(Message message, Channel channel) throws IOException {
        try {
            ThumbEvent event = thumbEventDecoder.decode(message);
            // executeWithoutResult returns only after the MySQL transaction commits.
            transactionTemplate.executeWithoutResult(status -> syncCurrentRedisState(event));
            if (event.getEventTime() != null) {
                thumbMetrics.recordProjectionLatency(Duration.between(event.getEventTime(), LocalDateTime.now()));
            }
            // In MANUAL mode this is the only point at which RabbitMQ deletes the delivery.
            channel.basicAck(message.getMessageProperties().getDeliveryTag(), false);
        } catch (Exception exception) {
            log.error("Failed to project thumb event into MySQL; sending to DLQ. deliveryTag={}, bodyBytes={}",
                    message.getMessageProperties().getDeliveryTag(), message.getBody().length, exception);
            thumbMetrics.recordConsumerNack();
            channel.basicNack(message.getMessageProperties().getDeliveryTag(), false, false);
        }
    }

    private void syncCurrentRedisState(ThumbEvent event) {
        boolean redisLiked = Boolean.TRUE.equals(redisTemplate.opsForHash().hasKey(
                RedisKeyUtil.getUserThumbKey(event.getUserId()), event.getBlogId().toString()));
        if (redisLiked) {
            com.yuyuan.thumb.model.entity.Thumb thumb = new com.yuyuan.thumb.model.entity.Thumb();
            thumb.setId(IdWorker.getId());
            thumb.setUserId(event.getUserId());
            thumb.setBlogId(event.getBlogId());
            boolean inserted = thumbMapper.insertIgnore(thumb) == 1;
            thumbMetrics.recordProjectionDelta("insert", inserted);
        } else {
            boolean deleted = thumbMapper.deleteByUserAndBlog(event.getUserId(), event.getBlogId()) == 1;
            thumbMetrics.recordProjectionDelta("delete", deleted);
        }
    }
}
