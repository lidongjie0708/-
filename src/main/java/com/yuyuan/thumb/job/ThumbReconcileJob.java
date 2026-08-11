package com.yuyuan.thumb.job;

import com.baomidou.mybatisplus.core.toolkit.IdWorker;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuyuan.thumb.config.RabbitMQConfig;
import com.yuyuan.thumb.constant.ThumbConstant;
import com.yuyuan.thumb.listener.thumb.msg.ThumbEvent;
import com.yuyuan.thumb.metrics.ThumbReconciliationMetrics;
import com.yuyuan.thumb.metrics.ThumbMetrics;
import com.yuyuan.thumb.model.entity.Thumb;
import com.yuyuan.thumb.service.OutboxEventService;
import com.yuyuan.thumb.service.ThumbService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.Cursor;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ScanOptions;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/** Repairs MySQL's asynchronous projection from Redis, the thumb-state source of truth. */
@Slf4j
@Component
public class ThumbReconcileJob {

    @Resource private RedisTemplate<String, Object> redisTemplate;
    @Resource @Qualifier("thumbServiceLocalCache") private ThumbService thumbService;
    @Resource private OutboxEventService outboxEventService;
    @Resource private ThumbReconciliationMetrics reconciliationMetrics;
    @Resource private ThumbMetrics thumbMetrics;
    @Value("${thumb.reconcile.max-mysql-rows:100000}") private long maxMysqlRows;
    @Value("${thumb.reconcile.mysql-page-size:1000}") private long mysqlPageSize;

    @Scheduled(cron = "${thumb.reconcile.cron:0 */5 * * * ?}")
    public void run() {
        try {
            Set<ThumbPair> redisPairs = scanRedisPairs();
            MysqlSnapshot mysql = scanMysqlPairs();
            if (!mysql.complete()) {
                reconciliationMetrics.recordIncomplete(redisPairs.size(), mysql.pairs().size());
                return;
            }
            Set<ThumbPair> redisOnly = new HashSet<>(redisPairs);
            redisOnly.removeAll(mysql.pairs());
            Set<ThumbPair> mysqlOnly = new HashSet<>(mysql.pairs());
            mysqlOnly.removeAll(redisPairs);
            reconciliationMetrics.recordComplete(redisOnly.size(), mysqlOnly.size(), redisPairs.size(), mysql.pairs().size());
            thumbMetrics.recordReconciledRepairs((long) redisOnly.size() + mysqlOnly.size());
            thumbMetrics.setConsistencyGap((long) redisPairs.size() - mysql.pairs().size());
            redisOnly.forEach(pair -> enqueue(pair, true));
            mysqlOnly.forEach(pair -> enqueue(pair, false));
        } catch (Exception exception) {
            reconciliationMetrics.recordIncomplete(0, 0);
            log.error("Thumb reconciliation failed", exception);
        }
    }

    private Set<ThumbPair> scanRedisPairs() {
        Set<ThumbPair> pairs = new HashSet<>();
        try (Cursor<String> cursor = redisTemplate.scan(ScanOptions.scanOptions()
                .match(ThumbConstant.USER_THUMB_KEY_PREFIX + "*").count(1000).build())) {
            while (cursor.hasNext()) {
                String key = cursor.next();
                String suffix = key.substring(ThumbConstant.USER_THUMB_KEY_PREFIX.length());
                // Skip non-user keys that share the prefix (delta/batch/lock/benchmark keys).
                if (!suffix.matches("\\d+")) {
                    continue;
                }
                Long userId = Long.valueOf(suffix);
                for (Object blogId : redisTemplate.opsForHash().keys(key)) pairs.add(new ThumbPair(userId, Long.valueOf(blogId.toString())));
            }
        }
        return pairs;
    }

    private MysqlSnapshot scanMysqlPairs() {
        Set<ThumbPair> pairs = new HashSet<>();
        for (long current = 1; pairs.size() < maxMysqlRows; current++) {
            List<Thumb> records = thumbService.page(new Page<>(current, mysqlPageSize, false)).getRecords();
            records.forEach(thumb -> pairs.add(new ThumbPair(thumb.getUserId(), thumb.getBlogId())));
            if (records.size() < mysqlPageSize) return new MysqlSnapshot(pairs, true);
        }
        return new MysqlSnapshot(pairs, false);
    }

    private void enqueue(ThumbPair pair, boolean desiredLiked) {
        ThumbEvent event = ThumbEvent.builder().eventId(UUID.randomUUID().toString()).userId(pair.userId())
                .blogId(pair.blogId()).desiredLiked(desiredLiked).version(IdWorker.getId()).eventTime(LocalDateTime.now()).build();
        outboxEventService.create("THUMB_STATE", "THUMB", pair.userId() + ":" + pair.blogId(),
                RabbitMQConfig.THUMB_EXCHANGE, RabbitMQConfig.THUMB_ROUTING_KEY, event);
    }

    private record ThumbPair(Long userId, Long blogId) { }
    private record MysqlSnapshot(Set<ThumbPair> pairs, boolean complete) { }
}
