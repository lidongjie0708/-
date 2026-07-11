package com.yuyuan.thumb.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuyuan.thumb.config.RabbitMQConfig;
import com.yuyuan.thumb.constant.RedisLuaScriptConstant;
import com.yuyuan.thumb.listener.thumb.msg.ThumbEvent;
import com.yuyuan.thumb.manager.cache.CacheManager;
import com.yuyuan.thumb.mapper.ThumbMapper;
import com.yuyuan.thumb.model.dto.thumb.DoThumbRequest;
import com.yuyuan.thumb.model.entity.Thumb;
import com.yuyuan.thumb.model.entity.User;
import com.yuyuan.thumb.model.enums.LuaStatusEnum;
import com.yuyuan.thumb.service.ThumbService;
import com.yuyuan.thumb.service.UserService;
import com.yuyuan.thumb.util.RedisKeyUtil;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service("thumbServiceRabbitMQ")
@Slf4j
@RequiredArgsConstructor
public class ThumbServiceRabbitMQImpl extends ServiceImpl<ThumbMapper, Thumb>
        implements ThumbService {

    private final UserService userService;
    private final RedisTemplate<String, Object> redisTemplate;
    private final RabbitTemplate rabbitTemplate;
    private final CacheManager cacheManager;

    @Override
    public Boolean doThumb(DoThumbRequest doThumbRequest, HttpServletRequest request) {
        if (doThumbRequest == null || doThumbRequest.getBlogId() == null) {
            throw new RuntimeException("参数错误");
        }

        User loginUser = userService.getLoginUser(request);
        Long loginUserId = loginUser.getId();
        Long blogId = doThumbRequest.getBlogId();
        String userThumbKey = RedisKeyUtil.getUserThumbKey(loginUserId);

        long result = redisTemplate.execute(
                RedisLuaScriptConstant.THUMB_SCRIPT_MQ,
                List.of(userThumbKey),
                blogId
        );
        if (LuaStatusEnum.FAIL.getValue() == result) {
            throw new RuntimeException("用户已点赞");
        }

        ThumbEvent thumbEvent = ThumbEvent.builder()
                .blogId(blogId)
                .userId(loginUserId)
                .type(ThumbEvent.EventType.INCR)
                .eventTime(LocalDateTime.now())
                .build();

        try {
            rabbitTemplate.convertAndSend(
                    RabbitMQConfig.THUMB_EXCHANGE,
                    RabbitMQConfig.THUMB_ROUTING_KEY,
                    thumbEvent
            );
            cacheManager.putIfPresent(userThumbKey, blogId.toString(), true);
        } catch (Exception ex) {
            redisTemplate.opsForHash().delete(userThumbKey, blogId.toString());
            log.error("Send thumb event failed, userId={}, blogId={}", loginUserId, blogId, ex);
            throw new RuntimeException("点赞失败，请稍后重试");
        }

        return true;
    }

    @Override
    public Boolean undoThumb(DoThumbRequest doThumbRequest, HttpServletRequest request) {
        if (doThumbRequest == null || doThumbRequest.getBlogId() == null) {
            throw new RuntimeException("参数错误");
        }

        User loginUser = userService.getLoginUser(request);
        Long loginUserId = loginUser.getId();
        Long blogId = doThumbRequest.getBlogId();
        String userThumbKey = RedisKeyUtil.getUserThumbKey(loginUserId);

        long result = redisTemplate.execute(
                RedisLuaScriptConstant.UNTHUMB_SCRIPT_MQ,
                List.of(userThumbKey),
                blogId
        );
        if (LuaStatusEnum.FAIL.getValue() == result) {
            throw new RuntimeException("用户未点赞");
        }

        ThumbEvent thumbEvent = ThumbEvent.builder()
                .blogId(blogId)
                .userId(loginUserId)
                .type(ThumbEvent.EventType.DECR)
                .eventTime(LocalDateTime.now())
                .build();

        try {
            rabbitTemplate.convertAndSend(
                    RabbitMQConfig.THUMB_EXCHANGE,
                    RabbitMQConfig.THUMB_ROUTING_KEY,
                    thumbEvent
            );
            cacheManager.putIfPresent(userThumbKey, blogId.toString(), null);
        } catch (Exception ex) {
            redisTemplate.opsForHash().put(userThumbKey, blogId.toString(), true);
            log.error("Send unthumb event failed, userId={}, blogId={}", loginUserId, blogId, ex);
            throw new RuntimeException("取消点赞失败，请稍后重试");
        }

        return true;
    }

    @Override
    public Boolean hasThumb(Long blogId, Long userId) {
        Object value = cacheManager.get(RedisKeyUtil.getUserThumbKey(userId), blogId.toString());
        return value != null;
    }
}
