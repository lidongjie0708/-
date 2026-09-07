ALTER TABLE rag_conversation_summary
  ADD COLUMN summary_json JSON NULL AFTER summary_text,
  ADD COLUMN last_summarized_turn_id BIGINT NOT NULL DEFAULT 0 AFTER turn_count,
  ADD COLUMN version INT NOT NULL DEFAULT 1 AFTER last_summarized_turn_id,
  ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'READY' AFTER version;

CREATE TABLE rag_memory_summary_task (
  id BIGINT NOT NULL AUTO_INCREMENT,
  session_id VARCHAR(128) NOT NULL,
  user_key VARCHAR(64) NOT NULL,
  user_id BIGINT NULL,
  target_turn_id BIGINT NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'PENDING',
  attempt_count INT NOT NULL DEFAULT 0,
  error_message TEXT NULL,
  locked_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_rag_summary_task_session_user (session_id, user_key),
  KEY idx_rag_summary_task_status_updated (status, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Durable async jobs for RAG memory summaries';
