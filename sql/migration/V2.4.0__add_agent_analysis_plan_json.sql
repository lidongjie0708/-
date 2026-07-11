-- Store operations analytics Agent execution trace.

ALTER TABLE `agent_analysis_log`
    ADD COLUMN `plan_json` JSON NULL COMMENT 'Execution plan and trace' AFTER `suggestions_json`;
