package com.yuyuan.thumb.listener.thumb;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.rabbitmq.client.Channel;
import com.yuyuan.thumb.config.RabbitMQConfig;
import com.yuyuan.thumb.listener.thumb.msg.ThumbEvent;
import com.yuyuan.thumb.manager.cache.CacheManager;
import com.yuyuan.thumb.mapper.BlogMapper;
import com.yuyuan.thumb.model.entity.Thumb;
import com.yuyuan.thumb.service.ThumbService;
import com.yuyuan.thumb.util.RedisKeyUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * RabbitMQ点赞消费者
 */
@Service
@Slf4j
public class RabbitThumbConsumer {

    private final BlogMapper blogMapper;
    private final ThumbService thumbService;
    private final CacheManager cacheManager;
    private final RedisTemplate<String, Object> redisTemplate;

    public RabbitThumbConsumer(BlogMapper blogMapper, 
                           @Qualifier("thumbServiceRabbitMQ") ThumbService thumbService,
                           CacheManager cacheManager,
                           RedisTemplate<String, Object> redisTemplate) {
        this.blogMapper = blogMapper;
        this.thumbService = thumbService;
        this.cacheManager = cacheManager;
        this.redisTemplate = redisTemplate;
    }

    /**
     * 处理死信队列消息
     */
    @RabbitListener(queues = RabbitMQConfig.THUMB_DLQ_QUEUE)
    public void consumeDlq(ThumbEvent event, Message message, Channel channel) throws IOException {
        log.info("DLQ message received: userId={}, blogId={}", event.getUserId(), event.getBlogId());
        log.info("消息已入库，已通知相关人员处理");
        channel.basicAck(message.getMessageProperties().getDeliveryTag(), false);
    }

    /**
     * 批量处理点赞消息
     */
    @RabbitListener(queues = RabbitMQConfig.THUMB_QUEUE, containerFactory = "rabbitListenerContainerFactory")
    @Transactional(rollbackFor = Exception.class)
    public void processThumbEvent(ThumbEvent event, Message message, Channel channel) throws IOException {
        try {
            log.info("Processing thumb event: userId={}, blogId={}, type={}", 
                    event.getUserId(), event.getBlogId(), event.getType());
            
            Map<Long, Long> countMap = new ConcurrentHashMap<>();
            List<Thumb> thumbs = new ArrayList<>();
            LambdaQueryWrapper<Thumb> wrapper = new LambdaQueryWrapper<>();
            boolean needRemove = false;

            if (event.getType() == ThumbEvent.EventType.INCR) {
                countMap.put(event.getBlogId(), 1L);
                Thumb thumb = new Thumb();
                thumb.setBlogId(event.getBlogId());
                thumb.setUserId(event.getUserId());
                thumbs.add(thumb);
            } else {
                needRemove = true;
                wrapper.eq(Thumb::getUserId, event.getUserId())
                       .eq(Thumb::getBlogId, event.getBlogId());
                countMap.put(event.getBlogId(), -1L);
            }

            // 批量更新数据库
            if (needRemove) {
                thumbService.remove(wrapper);
            }
            batchUpdateBlogs(countMap);
            batchInsertThumbs(thumbs);

            // 手动确认消息
            channel.basicAck(message.getMessageProperties().getDeliveryTag(), false);
            
        } catch (Exception e) {
            log.error("处理点赞消息失败", e);
            // 拒绝消息，进入死信队列
            channel.basicNack(message.getMessageProperties().getDeliveryTag(), false, false);
        }
    }

    public void batchUpdateBlogs(Map<Long, Long> countMap) {
        if (!countMap.isEmpty()) {
            blogMapper.batchUpdateThumbCount(countMap);
        }
    }

    public void batchInsertThumbs(List<Thumb> thumbs) {
        if (!thumbs.isEmpty()) {
            thumbService.saveBatch(thumbs, 500);
        }
    }
}
