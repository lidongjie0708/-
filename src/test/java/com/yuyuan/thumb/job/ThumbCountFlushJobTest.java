package com.yuyuan.thumb.job;

import com.yuyuan.thumb.mapper.BlogMapper;
import com.yuyuan.thumb.mapper.ThumbFlushBatchMapper;
import org.junit.jupiter.api.Test;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.data.redis.core.HashOperations;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.support.TransactionCallback;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ThumbCountFlushJobTest {

    private static final String FLUSHING_KEY = "thumb:blog:delta:flushing";
    private static final String BATCH_KEY = "thumb:blog:delta:flushing:batch";

    @Test
    void chunkifySplitsMapIntoBoundedChunks() {
        Map<Long, Long> deltas = new HashMap<>();
        for (long i = 1; i <= 5; i++) {
            deltas.put(i, i);
        }

        List<Map<Long, Long>> chunks = ThumbCountFlushJob.chunkify(deltas, 2);

        assertThat(chunks).hasSize(3);
        assertThat(chunks.get(0)).hasSize(2);
        assertThat(chunks.get(1)).hasSize(2);
        assertThat(chunks.get(2)).hasSize(1);
        long total = chunks.stream().flatMap(c -> c.values().stream()).mapToLong(Long::longValue).sum();
        assertThat(total).isEqualTo(15);
    }

    @Test
    void chunkifyHandlesEmptyAndInvalidBatchSize() {
        assertThat(ThumbCountFlushJob.chunkify(new HashMap<>(), 100)).isEmpty();
        assertThat(ThumbCountFlushJob.chunkify(null, 100)).isEmpty();
        assertThat(ThumbCountFlushJob.chunkify(Map.of(1L, 1L), 0)).hasSize(1);
    }

    @Test
    void flushSkipsAlreadyAppliedBatchWithoutTouchingBlogTable() {
        RedisTemplate<String, Object> redisTemplate = mock(RedisTemplate.class);
        ValueOperations<String, Object> valueOps = mock(ValueOperations.class);
        HashOperations<String, Object, Object> hashOps = mock(HashOperations.class);
        when(redisTemplate.opsForValue()).thenReturn(valueOps);
        when(redisTemplate.opsForHash()).thenReturn(hashOps);
        when(valueOps.get(BATCH_KEY)).thenReturn("batch-1");
        when(redisTemplate.hasKey(FLUSHING_KEY)).thenReturn(true);
        when(hashOps.entries(FLUSHING_KEY)).thenReturn(Map.of("101", 2L));

        ThumbFlushBatchMapper batchMapper = mock(ThumbFlushBatchMapper.class);
        when(batchMapper.insertIgnore("batch-1")).thenReturn(0);
        BlogMapper blogMapper = mock(BlogMapper.class);
        ThumbCountFlushJob job = buildJob(redisTemplate, blogMapper, batchMapper);

        job.flush();

        verify(blogMapper, never()).batchUpdateThumbCount(any());
        verify(redisTemplate, atLeastOnce()).delete(any(List.class));
    }

    @Test
    void flushAppliesNewBatchInChunks() {
        RedisTemplate<String, Object> redisTemplate = mock(RedisTemplate.class);
        ValueOperations<String, Object> valueOps = mock(ValueOperations.class);
        HashOperations<String, Object, Object> hashOps = mock(HashOperations.class);
        when(redisTemplate.opsForValue()).thenReturn(valueOps);
        when(redisTemplate.opsForHash()).thenReturn(hashOps);
        when(valueOps.get(BATCH_KEY)).thenReturn("batch-2");
        when(redisTemplate.hasKey(FLUSHING_KEY)).thenReturn(true);
        Map<Object, Object> deltas = new HashMap<>();
        for (long i = 1; i <= 5; i++) {
            deltas.put(String.valueOf(i), i);
        }
        when(hashOps.entries(FLUSHING_KEY)).thenReturn(deltas);

        ThumbFlushBatchMapper batchMapper = mock(ThumbFlushBatchMapper.class);
        when(batchMapper.insertIgnore(anyString())).thenReturn(1);
        BlogMapper blogMapper = mock(BlogMapper.class);
        ThumbCountFlushJob job = buildJob(redisTemplate, blogMapper, batchMapper);
        ReflectionTestUtils.setField(job, "batchSize", 2);

        job.flush();

        verify(blogMapper, times(3)).batchUpdateThumbCount(any());
    }

    private ThumbCountFlushJob buildJob(RedisTemplate<String, Object> redisTemplate,
                                        BlogMapper blogMapper,
                                        ThumbFlushBatchMapper batchMapper) {
        TransactionTemplate tx = mock(TransactionTemplate.class);
        when(tx.execute(any(TransactionCallback.class))).thenAnswer(invocation -> {
            TransactionCallback<Boolean> callback = invocation.getArgument(0);
            return callback.doInTransaction(null);
        });
        RLock lock = mock(RLock.class);
        try {
            when(lock.tryLock(1, TimeUnit.SECONDS)).thenReturn(true);
        } catch (InterruptedException e) {
            throw new IllegalStateException(e);
        }
        when(lock.isHeldByCurrentThread()).thenReturn(true);
        RedissonClient redisson = mock(RedissonClient.class);
        when(redisson.getLock("thumb:count:flush:lock")).thenReturn(lock);
        ThumbCountFlushJob job = new ThumbCountFlushJob(redisTemplate, blogMapper, batchMapper, redisson, tx);
        ReflectionTestUtils.setField(job, "batchSize", 1000);
        return job;
    }
}
