package com.yuyuan.thumb.service.impl;

import com.yuyuan.thumb.model.entity.Blog;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.HashOperations;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class BlogServiceImplTest {

    @Test
    void fillRealTimeThumbCountsCombinesMysqlBaseWithPendingDelta() {
        RedisTemplate<String, Object> redisTemplate = mock(RedisTemplate.class);
        HashOperations<String, Object, Object> hashOps = mock(HashOperations.class);
        when(redisTemplate.opsForHash()).thenReturn(hashOps);
        when(hashOps.multiGet(eq("thumb:blog:delta"), anyList()))
                .thenReturn(Arrays.asList(5L, null, -3L, "7"));

        BlogServiceImpl service = new BlogServiceImpl();
        ReflectionTestUtils.setField(service, "redisTemplate", redisTemplate);

        Blog b1 = blog(1L, 10);
        Blog b2 = blog(2L, 3);
        Blog b3 = blog(3L, 1);
        Blog b4 = blog(4L, null);
        service.fillRealTimeThumbCounts(List.of(b1, b2, b3, b4));

        assertThat(b1.getThumbCount()).isEqualTo(15);  // 10 + 5
        assertThat(b2.getThumbCount()).isEqualTo(3);   // no pending delta
        assertThat(b3.getThumbCount()).isZero();       // clamped at 0 (1 + (-3))
        assertThat(b4.getThumbCount()).isEqualTo(7);   // null base + 7
    }

    private Blog blog(Long id, Integer thumbCount) {
        Blog blog = new Blog();
        blog.setId(id);
        blog.setThumbCount(thumbCount);
        return blog;
    }
}
