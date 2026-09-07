-- Evidence-backed findings emitted by the operations growth Agent.  Agent code may
-- create records through the application integration boundary; this table is never
-- used as a command channel for publishing or modifying user content.
CREATE TABLE IF NOT EXISTS `operation_finding` (
    `id` CHAR(36) NOT NULL,
    `finding_type` VARCHAR(64) NOT NULL,
    `status` VARCHAR(32) NOT NULL,
    `target_type` VARCHAR(64) NOT NULL,
    `target_id` VARCHAR(128) NOT NULL,
    `metric_key` VARCHAR(128) NOT NULL,
    `metric_version` VARCHAR(32) NOT NULL,
    `current_value` DECIMAL(20, 6) NULL,
    `baseline_value` DECIMAL(20, 6) NULL,
    `anomaly_score` DECIMAL(20, 6) NULL,
    `confidence` DECIMAL(5, 4) NULL,
    `sample_size` INT NULL,
    `observed_from` DATETIME NULL,
    `observed_to` DATETIME NULL,
    `data_fresh_at` DATETIME NULL,
    `evidence_json` JSON NULL,
    `limitations_json` JSON NULL,
    `analysis_log_id` BIGINT NULL,
    `created_by` BIGINT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_operation_finding_status_created` (`status`, `created_at`),
    INDEX `idx_operation_finding_type_observed` (`finding_type`, `observed_to`),
    INDEX `idx_operation_finding_target` (`target_type`, `target_id`),
    INDEX `idx_operation_finding_analysis_log` (`analysis_log_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Evidence-backed operations growth findings';

-- Observation records deliberately model before/after measurements, not causal
-- claims. A single action can have several metric observations.
CREATE TABLE IF NOT EXISTS `operation_experiment` (
    `id` CHAR(36) NOT NULL,
    `action_id` CHAR(36) NOT NULL,
    `metric_key` VARCHAR(128) NOT NULL,
    `metric_version` VARCHAR(32) NOT NULL,
    `baseline_snapshot_json` JSON NULL,
    `post_snapshot_json` JSON NULL,
    `observation_from` DATETIME NULL,
    `observation_to` DATETIME NULL,
    `status` VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    `attribution_result` VARCHAR(64) NULL,
    `not_attributable_reason` VARCHAR(500) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_operation_experiment_action_created` (`action_id`, `created_at`),
    INDEX `idx_operation_experiment_status_observed` (`status`, `observation_to`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Non-causal operation action observations';
