-- Online RAG observations and offline evaluation runs have different retention,
-- query patterns, and schemas. Keep the legacy rag_eval_log table untouched for
-- historical data; all new writes use the tables below.

CREATE TABLE IF NOT EXISTS `rag_observation_log` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `question` VARCHAR(1000) NOT NULL,
    `answer` LONGTEXT NULL,
    `user_id` BIGINT NULL,
    `role` VARCHAR(50) NULL,
    `confidence` DOUBLE NULL,
    `citation_count` INT NOT NULL DEFAULT 0,
    `context_precision_lite` DOUBLE NULL,
    `answer_grounding_lite` DOUBLE NULL,
    `has_citations` TINYINT NOT NULL DEFAULT 0,
    `query_rewrite_json` JSON NULL,
    `citations_json` JSON NULL,
    `context_optimization_json` JSON NULL,
    `retrieval_trace_json` JSON NULL,
    `cache_json` JSON NULL,
    `evaluation_json` JSON NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_rag_observation_created_at` (`created_at`),
    INDEX `idx_rag_observation_user_id` (`user_id`),
    INDEX `idx_rag_observation_has_citations` (`has_citations`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Online RAG request observations';

CREATE TABLE IF NOT EXISTS `rag_eval_run` (
    `id` CHAR(36) NOT NULL,
    `requested_framework` VARCHAR(32) NOT NULL,
    `framework` VARCHAR(32) NULL,
    `status` VARCHAR(24) NOT NULL,
    `case_count` INT NOT NULL DEFAULT 0,
    `user_id` BIGINT NULL,
    `role` VARCHAR(50) NULL,
    `visible_scopes_json` JSON NULL,
    `config_json` JSON NULL,
    `summary_json` JSON NULL,
    `fallback_reason` TEXT NULL,
    `error_message` TEXT NULL,
    `started_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `finished_at` DATETIME NULL,
    PRIMARY KEY (`id`),
    INDEX `idx_rag_eval_run_started_at` (`started_at`),
    INDEX `idx_rag_eval_run_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Offline RAG evaluation runs';

CREATE TABLE IF NOT EXISTS `rag_eval_case_result` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `run_id` CHAR(36) NOT NULL,
    `case_index` INT NOT NULL,
    `question` VARCHAR(1000) NOT NULL,
    `ground_truth` LONGTEXT NULL,
    `reference_answer` LONGTEXT NULL,
    `expected_keywords_json` JSON NULL,
    `answer` LONGTEXT NULL,
    `contexts_json` JSON NULL,
    `citations_json` JSON NULL,
    `faithfulness` DOUBLE NULL,
    `answer_relevancy` DOUBLE NULL,
    `context_precision` DOUBLE NULL,
    `context_recall` DOUBLE NULL,
    `context_precision_lite` DOUBLE NULL,
    `answer_grounding_lite` DOUBLE NULL,
    `keyword_hit_rate` DOUBLE NULL,
    `has_citations` TINYINT NOT NULL DEFAULT 0,
    `evaluation_json` JSON NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_rag_eval_case_run_index` (`run_id`, `case_index`),
    INDEX `idx_rag_eval_case_run_id` (`run_id`),
    CONSTRAINT `fk_rag_eval_case_run`
        FOREIGN KEY (`run_id`) REFERENCES `rag_eval_run` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Per-case results for offline RAG evaluations';
