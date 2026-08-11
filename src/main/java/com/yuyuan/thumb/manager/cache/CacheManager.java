package com.yuyuan.thumb.manager.cache;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.binder.cache.CaffeineCacheMetrics;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 缓存类
 *
 * @author pine
 */
@Component
@Slf4j
public class CacheManager {

    /** Sentinel cached for "queried but not liked" so Caffeine can store the negative result. */
    private static final Object NEGATIVE = new Object();

    private TopK hotKeyDetector;

    private Cache<String, Object> localCache;

    private final AtomicLong hotKeyCount = new AtomicLong();
    private Counter redisReadsSaved;
    private Counter hotKeyPromoted;
    private Counter hotKeyEvicted;

    @Resource
    private RedisTemplate<String, Object> redisTemplate;

    @Resource
    private MeterRegistry meterRegistry;

    @Bean
    public TopK getHotKeyDetector() {
        hotKeyDetector = new HeavyKeeper(
                // 监控 Top 100 Key
                100,
                // 哈希表宽度
                100000,
                // 哈希表深度
                5,
                // 衰减系数
                0.92,
                // 最小出现 10 次才记录
                10
        );
        return hotKeyDetector;
    }

    @Bean
    public Cache<String, Object> localCache() {
        localCache = Caffeine.newBuilder()
                .maximumSize(1000)
                .expireAfterWrite(5, TimeUnit.MINUTES)
                // Keep hit/miss counters so Micrometer can expose cache_gets_total by result.
                .recordStats()
                .build();
        CaffeineCacheMetrics.monitor(meterRegistry, localCache, "thumbLocalCache");
        return localCache;
    }

    @PostConstruct
    public void initMetrics() {
        redisReadsSaved = Counter.builder("thumb.cache.redis.reads.saved")
                .description("Redis reads avoided by local cache hits")
                .register(meterRegistry);
        hotKeyPromoted = Counter.builder("thumb.cache.hotkey.promoted.total")
                .description("Hot keys promoted from Redis into the local cache")
                .register(meterRegistry);
        hotKeyEvicted = Counter.builder("thumb.cache.hotkey.evicted.total")
                .description("Hot keys expelled from the HeavyKeeper top-K set")
                .register(meterRegistry);
        Gauge.builder("thumb.cache.hotkey.current", hotKeyCount, AtomicLong::get)
                .description("Current number of tracked hot keys")
                .register(meterRegistry);
    }

    // 辅助方法：构造复合 key
    private String buildCacheKey(String hashKey, String key) {
        return hashKey + ":" + key;
    }

    public Object get(String hashKey, String key) {
        // 构造唯一的 composite key
        String compositeKey = buildCacheKey(hashKey, key);

        // 1. 先查本地缓存
        Object cached = localCache.getIfPresent(compositeKey);
        if (cached != null) {
            redisReadsSaved.increment();
            // 记录访问次数（每次访问计数 +1）
            hotKeyDetector.add(compositeKey, 1);
            return NEGATIVE.equals(cached) ? null : cached;
        }

        // 2. 本地缓存未命中，查询 Redis
        Object redisValue = redisTemplate.opsForHash().get(hashKey, key);

        // 3. 记录访问（计数 +1）
        AddResult addResult = hotKeyDetector.add(compositeKey, 1);

        // 4. 如果是热 Key 且不在本地缓存，则缓存数据（未点赞用哨兵，避免 Caffeine 无法缓存 null）
        if (addResult.isHotKey()) {
            localCache.put(compositeKey, redisValue != null ? redisValue : NEGATIVE);
            hotKeyPromoted.increment();
        }

        return redisValue;
    }

    /**
     * 点赞/取消时主动维护本地缓存：
     * value 非 null（点赞）→ 覆盖缓存（含负缓存）；value 为 null（取消）→ 删除缓存。
     */
    public void put(String hashKey, String key, Object value) {
        String compositeKey = buildCacheKey(hashKey, key);
        if (value == null) {
            localCache.invalidate(compositeKey);
        } else {
            localCache.put(compositeKey, value);
        }
    }

    // 定时清理过期的热 Key 检测数据
    @Scheduled(fixedRate = 20, timeUnit = TimeUnit.SECONDS)
    public void cleanHotKeys() {
        hotKeyDetector.fading();
        refreshHotKeyMetrics();
    }

    private void refreshHotKeyMetrics() {
        hotKeyCount.set(hotKeyDetector.list().size());
        Item item;
        while ((item = hotKeyDetector.expelled().poll()) != null) {
            hotKeyEvicted.increment();
        }
    }
}
