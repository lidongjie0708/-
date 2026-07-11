-- RAG observation log.
-- Stores every RAG answer's retrieval, citation, and lightweight evaluation data.

CREATE TABLE IF NOT EXISTS `rag_eval_log` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    `question` VARCHAR(1000) NOT NULL COMMENT 'User question',
    `answer` LONGTEXT NULL COMMENT 'RAG answer',
    `user_id` BIGINT NULL COMMENT 'Question user id',
    `role` VARCHAR(50) NULL COMMENT 'Question role',
    `confidence` DOUBLE NULL COMMENT 'Top rerank/vector confidence',
    `citation_count` INT DEFAULT 0 COMMENT 'Number of citations used',
    `context_precision_lite` DOUBLE NULL COMMENT 'Lite retrieval relevance metric',
    `answer_grounding_lite` DOUBLE NULL COMMENT 'Lite grounding metric',
    `has_citations` TINYINT DEFAULT 0 COMMENT 'Whether answer has citations',
    `keyword_hit_rate` DOUBLE NULL COMMENT 'Optional eval keyword hit rate',
    `query_rewrite_json` JSON NULL COMMENT 'Query rewrite payload',
    `citations_json` JSON NULL COMMENT 'Citation payload',
    `evaluation_json` JSON NULL COMMENT 'Evaluation payload',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Create time',
    PRIMARY KEY (`id`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_user_id` (`user_id`),
    INDEX `idx_has_citations` (`has_citations`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RAG answer observation log';
