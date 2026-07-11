-- ============================================================
-- Agent 嵌入功能 - 数据库迁移脚本 V2.0.0
-- 用途：为 blog 表和 comments 表添加 Agent 相关字段
-- 执行方式：直接在 MySQL 中执行此脚本
-- 注意：所有新增字段均允许为 NULL，兼容已有数据
-- ============================================================

-- ========== 1. blog 表扩展 ==========
ALTER TABLE blog
    ADD COLUMN `summary`         VARCHAR(500)  DEFAULT NULL COMMENT '博客摘要（Agent 自动生成）' AFTER `thumbCount`,
    ADD COLUMN `tags`            VARCHAR(200)  DEFAULT NULL COMMENT '标签（Agent 推荐，逗号分隔）' AFTER `summary`,
    ADD COLUMN `embedding_status` TINYINT      DEFAULT 0    COMMENT '向量化状态：0-未处理 1-处理中 2-已完成 3-失败' AFTER `tags`,
    ADD COLUMN `audit_status`    TINYINT      DEFAULT 0    COMMENT '审核状态：0-待审核 1-通过 2-拒绝' AFTER `embedding_status`;

-- 为 embedding_status 和 audit_status 添加索引（方便定时任务批量处理）
ALTER TABLE blog
    ADD INDEX `idx_embedding_status` (`embedding_status`),
    ADD INDEX `idx_audit_status` (`audit_status`);

-- ========== 2. comments 表扩展 ==========
ALTER TABLE comments
    ADD COLUMN `sentiment_score` INT           DEFAULT NULL COMMENT '情感得分（Agent 分析，范围 -100~100）' AFTER `content`,
    ADD COLUMN `is_flagged`      TINYINT       DEFAULT 0    COMMENT '是否被标记违规：0-正常 1-标记违规' AFTER `sentiment_score`;

-- 为 is_flagged 添加索引（方便筛选违规评论）
ALTER TABLE comments
    ADD INDEX `idx_is_flagged` (`is_flagged`);
