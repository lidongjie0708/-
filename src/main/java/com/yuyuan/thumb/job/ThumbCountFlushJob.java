package com.yuyuan.thumb.job;

import com.yuyuan.thumb.mapper.BlogMapper;
import com.yuyuan.thumb.mapper.ThumbFlushBatchMapper;
import com.yuyuan.thumb.util.RedisKeyUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * Flushes per-blog like-count deltas from Redis to MySQL in batched UPDATEs.
 *
 * <p>Multi-instance safety:
 * <ul>
 *   <li>A Redisson lock guarantees only one instance flushes at a time.</li>
 *   <li>The batch id is written atomically with RENAME, so retries reuse the same id.</li>
 *   <li>INSERT IGNORE on thumb_flush_batch makes re-applying the same batch a no-op,
 *       covering the crash window between the MySQL commit and the Redis key cleanup.</li>
 *   <li>The delta map is split into bounded chunks so one flush never builds a giant SQL.</li>
 * </ul>
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ThumbCountFlushJob {

    private static final String FLUSH_LOCK_KEY = "thumb:count:flush:lock";
    private static final long BATCH_KEY_TTL_SECONDS = 3600;

    private final RedisTemplate<String, Object> redisTemplate;
    private final BlogMapper blogMapper;
    private final ThumbFlushBatchMapper thumbFlushBatchMapper;
    private final RedissonClient redissonClient;
    private final TransactionTemplate transactionTemplate;

    @Value("${thumb.flush.batch-size:1000}")
    private int batchSize;

    /**
     * Atomically moves the live delta hash to the flushing hash and records the batch id.
     * KEYS[1]=delta, KEYS[2]=flushing, KEYS[3]=batch key, ARGV[1]=batch id.
     */
    private static final RedisScript<Long> RENAME_WITH_BATCH = new DefaultRedisScript<>("""
            if redis.call('EXISTS', KEYS[1]) == 1 and redis.call('EXISTS', KEYS[2]) == 0 then
                redis.call('RENAME', KEYS[1], KEYS[2])
                redis.call('SET', KEYS[3], ARGV[1])
                redis.call('EXPIRE', KEYS[3], 3600)
                return 1
            end
            return 0
            """, Long.class);

    @Scheduled(fixedRate = 5000)
    public void flush() {
        RLock lock = redissonClient.getLock(FLUSH_LOCK_KEY);
        boolean locked;
        try {
            locked = lock.tryLock(1, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return;
        }
        if (!locked) {
            log.debug("Another instance is flushing thumb counts; skipping this cycle");
            return;
        }
        try {
            flushLocked();
        } finally {
            if (lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }

    private void flushLocked() {
        String deltaKey = RedisKeyUtil.getBlogDeltaKey();
        String flushingKey = RedisKeyUtil.getBlogDeltaFlushingKey();
        String batchKey = RedisKeyUtil.getBlogDeltaFlushingBatchKey();
        try {
            String batchId = resolveOrCreateBatch(deltaKey, flushingKey, batchKey);
            if (batchId == null) {
                return; // nothing to flush
            }
            Map<Object, Object> deltas = redisTemplate.opsForHash().entries(flushingKey);
            if (deltas.isEmpty()) {
                redisTemplate.delete(List.of(flushingKey, batchKey));
                return;
            }
            Map<Long, Long> countMap = new HashMap<>();
            deltas.forEach((blogId, value) ->
                    countMap.put(Long.valueOf(blogId.toString()), Long.valueOf(value.toString())));

            Boolean applied = transactionTemplate.execute(
                    status -> applyBatchIfNew(batchId, countMap));
            if (Boolean.TRUE.equals(applied)) {
                // The MySQL transaction committed; only now can the batch keys be released.
                redisTemplate.delete(List.of(flushingKey, batchKey));
            }
        } catch (Exception exception) {
            // Flushing key and batch id are kept so the next run retries the same deltas
            // with the same id, which makes the retry idempotent.
            log.error("Thumb count flush failed; deltas retained for retry", exception);
        }
    }

    private String resolveOrCreateBatch(String deltaKey, String flushingKey, String batchKey) {
        Object existingBatch = redisTemplate.opsForValue().get(batchKey);
        if (existingBatch != null) {
            return existingBatch.toString();
        }
        if (Boolean.TRUE.equals(redisTemplate.hasKey(flushingKey))) {
            // Leftover flushing hash without a batch id (e.g. produced before this change):
            // claim it with a new id so every retry of this batch stays idempotent.
            String batchId = UUID.randomUUID().toString();
            redisTemplate.opsForValue().set(batchKey, batchId, BATCH_KEY_TTL_SECONDS, TimeUnit.SECONDS);
            return batchId;
        }
        String batchId = UUID.randomUUID().toString();
        Long renamed = redisTemplate.execute(RENAME_WITH_BATCH, List.of(deltaKey, flushingKey, batchKey), batchId);
        if (renamed == null || renamed == 0L) {
            return null;
        }
        return batchId;
    }

    private Boolean applyBatchIfNew(String batchId, Map<Long, Long> countMap) {
        if (thumbFlushBatchMapper.insertIgnore(batchId) == 0) {
            // The batch was committed by a previous run that crashed before releasing the keys.
            log.warn("Flush batch {} was already applied; skipping to avoid double counting", batchId);
            redisTemplate.delete(List.of(RedisKeyUtil.getBlogDeltaFlushingKey(),
                    RedisKeyUtil.getBlogDeltaFlushingBatchKey()));
            return false;
        }
        for (Map<Long, Long> chunk : chunkify(countMap, batchSize)) {
            blogMapper.batchUpdateThumbCount(chunk);
        }
        return true;
    }

    static List<Map<Long, Long>> chunkify(Map<Long, Long> countMap, int batchSize) {
        List<Map<Long, Long>> chunks = new ArrayList<>();
        if (countMap == null || countMap.isEmpty()) {
            return chunks;
        }
        int size = Math.max(1, batchSize);
        Map<Long, Long> chunk = new HashMap<>();
        int count = 0;
        for (Map.Entry<Long, Long> entry : countMap.entrySet()) {
            chunk.put(entry.getKey(), entry.getValue());
            count++;
            if (count == size) {
                chunks.add(chunk);
                chunk = new HashMap<>();
                count = 0;
            }
        }
        if (!chunk.isEmpty()) {
            chunks.add(chunk);
        }
        return chunks;
    }

    @Scheduled(fixedRate = 600000)
    public void cleanupLedger() {
        try {
            int deleted = thumbFlushBatchMapper.deleteOlderThan(LocalDateTime.now().minusHours(1));
            if (deleted > 0) {
                log.info("Cleaned {} expired thumb flush batch ledger rows", deleted);
            }
        } catch (Exception exception) {
            log.warn("Failed to clean thumb flush batch ledger", exception);
        }
    }
}
