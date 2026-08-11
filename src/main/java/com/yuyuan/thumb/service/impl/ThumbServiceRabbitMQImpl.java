package com.yuyuan.thumb.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.baomidou.mybatisplus.core.toolkit.IdWorker;
import com.yuyuan.thumb.config.RabbitMQConfig;
import com.yuyuan.thumb.constant.RedisLuaScriptConstant;
import com.yuyuan.thumb.listener.thumb.msg.ThumbEvent;
import com.yuyuan.thumb.mapper.ThumbMapper;
import com.yuyuan.thumb.metrics.ThumbMetrics;
import com.yuyuan.thumb.model.dto.thumb.DoThumbRequest;
import com.yuyuan.thumb.model.entity.Thumb;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.service.ThumbService;
import com.yuyuan.thumb.service.UserService;
import com.yuyuan.thumb.util.RedisKeyUtil;
import com.yuyuan.thumb.util.UserContext;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

import java.util.List;
import java.time.LocalDateTime;
import java.util.UUID;

@Service("thumbServiceRabbitMQ")
@Slf4j
@RequiredArgsConstructor
public class ThumbServiceRabbitMQImpl extends ServiceImpl<ThumbMapper, Thumb>
        implements ThumbService {

    private final org.springframework.data.redis.core.RedisTemplate<String, Object> redisTemplate;
    private final RabbitTemplate rabbitTemplate;
    private final ThumbMetrics thumbMetrics;

    @Override
    public Boolean doThumb(DoThumbRequest doThumbRequest, HttpServletRequest request) {
        if (doThumbRequest == null || doThumbRequest.getBlogId() == null) {
            throw new RuntimeException("参数错误");
        }

        Long loginUserId = UserContext.getCurrentUserId();
        if (loginUserId == null) {
            throw new RuntimeException("not logged in");
        }
        Long blogId = doThumbRequest.getBlogId();
        String userThumbKey = RedisKeyUtil.getUserThumbKey(loginUserId);
        long result = redisTemplate.execute(
                RedisLuaScriptConstant.THUMB_SCRIPT_MQ_V2,
                List.of(userThumbKey, RedisKeyUtil.getBlogDeltaKey()),
                blogId, 1L);
        if (result < 0) {
            thumbMetrics.recordIdempotentReject("do");
            throw new RuntimeException("用户已点赞");
        }

        ThumbEvent thumbEvent = ThumbEvent.builder()
                .eventId(UUID.randomUUID().toString())
                .blogId(blogId)
                .userId(loginUserId)
                .desiredLiked(true)
                .version(IdWorker.getId())
                .eventTime(LocalDateTime.now())
                .build();

        try {
            rabbitTemplate.convertAndSend(RabbitMQConfig.THUMB_EXCHANGE,
                    RabbitMQConfig.THUMB_ROUTING_KEY, thumbEvent);
        } catch (RuntimeException exception) {
            redisTemplate.opsForHash().delete(userThumbKey, blogId.toString());
            redisTemplate.opsForHash().increment(RedisKeyUtil.getBlogDeltaKey(), blogId.toString(), -1L);
            throw exception;
        }

        return true;
    }

    @Override
    public Boolean undoThumb(DoThumbRequest doThumbRequest, HttpServletRequest request) {
        if (doThumbRequest == null || doThumbRequest.getBlogId() == null) {
            throw new RuntimeException("参数错误");
        }

        Long loginUserId = UserContext.getCurrentUserId();
        if (loginUserId == null) {
            throw new RuntimeException("not logged in");
        }
        Long blogId = doThumbRequest.getBlogId();
        String userThumbKey = RedisKeyUtil.getUserThumbKey(loginUserId);
        long result = redisTemplate.execute(
                RedisLuaScriptConstant.UNTHUMB_SCRIPT_MQ_V2,
                List.of(userThumbKey, RedisKeyUtil.getBlogDeltaKey()),
                blogId, -1L);
        if (result < 0) {
            thumbMetrics.recordIdempotentReject("undo");
            throw new RuntimeException("用户未点赞");
        }

        ThumbEvent thumbEvent = ThumbEvent.builder()
                .eventId(UUID.randomUUID().toString())
                .blogId(blogId)
                .userId(loginUserId)
                .desiredLiked(false)
                .version(IdWorker.getId())
                .eventTime(LocalDateTime.now())
                .build();

        try {
            rabbitTemplate.convertAndSend(RabbitMQConfig.THUMB_EXCHANGE,
                    RabbitMQConfig.THUMB_ROUTING_KEY, thumbEvent);
        } catch (RuntimeException exception) {
            redisTemplate.opsForHash().put(userThumbKey, blogId.toString(), true);
            redisTemplate.opsForHash().increment(RedisKeyUtil.getBlogDeltaKey(), blogId.toString(), 1L);
            throw exception;
        }

        return true;
    }

    @Override
    public Boolean hasThumb(Long blogId, Long userId) {
        return redisTemplate.opsForHash().hasKey(
                RedisKeyUtil.getUserThumbKey(userId), blogId.toString());
    }
}
