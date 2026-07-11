-- Operations analytics Agent observation log.

CREATE TABLE IF NOT EXISTS `agent_analysis_log` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    `question` VARCHAR(1000) NOT NULL COMMENT 'Admin question',
    `intent` VARCHAR(80) NULL COMMENT 'Detected analysis intent',
    `user_id` BIGINT NULL COMMENT 'Operator user id',
    `role` VARCHAR(50) NULL COMMENT 'Operator role',
    `sql_text` LONGTEXT NULL COMMENT 'Generated or template SQL',
    `status` VARCHAR(30) NOT NULL COMMENT 'SUCCESS/FAILED/DENIED',
    `row_count` INT DEFAULT 0 COMMENT 'Query row count',
    `confidence` DOUBLE NULL COMMENT 'Analysis confidence',
    `chart_json` JSON NULL COMMENT 'Chart config',
    `result_json` JSON NULL COMMENT 'Query result sample',
    `insight` LONGTEXT NULL COMMENT 'Generated insight',
    `suggestions_json` JSON NULL COMMENT 'Generated suggestions',
    `error_message` VARCHAR(1000) NULL COMMENT 'Error message',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Create time',
    PRIMARY KEY (`id`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_intent` (`intent`),
    INDEX `idx_status` (`status`),
    INDEX `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Operations analytics Agent log';
