-- 点赞计数批量落库的幂等台账：
-- flush 每批 delta 生成 batch_id（RENAME 时原子写入 Redis），
-- MySQL 侧 INSERT IGNORE 去重，保证"更新成功但删 key 前崩溃"的重试不会重复计数。
CREATE TABLE IF NOT EXISTS thumb_flush_batch (
    batch_id VARCHAR(64) NOT NULL COMMENT '幂等批次号',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '批次创建时间',
    PRIMARY KEY (batch_id),
    KEY idx_thumb_flush_batch_created_at (created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '点赞计数批量落库幂等台账';
