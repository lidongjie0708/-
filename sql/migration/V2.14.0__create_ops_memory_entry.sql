-- Operations agent long-term memory.

CREATE TABLE IF NOT EXISTS `ops_memory_entry` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    `scope` VARCHAR(16) NOT NULL COMMENT 'GLOBAL / USER / SESSION',
    `user_id` BIGINT NULL COMMENT 'Owner for USER scope; NULL for GLOBAL',
    `session_id` VARCHAR(128) NULL COMMENT 'Owner for SESSION scope; NULL for GLOBAL',
    `memory_key` VARCHAR(160) NOT NULL COMMENT 'Unique fact key inside its scope',
    `content` VARCHAR(500) NOT NULL COMMENT 'One-line durable fact',
    `importance` DECIMAL(3,2) NOT NULL DEFAULT 0.50 COMMENT '0.00-1.00 retention priority',
    `tags_json` JSON NULL COMMENT 'Searchable tags, e.g. ["preference","comment_quality"]',
    `embedding_json` JSON NULL COMMENT 'Optional vector payload for semantic recall',
    `expires_at` DATETIME NULL COMMENT 'Optional expiry; NULL means keep',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Create time',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_scope_owner_key` (`scope`, `user_id`, `session_id`, `memory_key`),
    INDEX `idx_scope_user_importance` (`scope`, `user_id`, `importance`),
    INDEX `idx_updated_at` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Operations agent long-term memory';
