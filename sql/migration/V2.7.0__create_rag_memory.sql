CREATE TABLE rag_conversation_turn (
  id BIGINT NOT NULL AUTO_INCREMENT,
  session_id VARCHAR(128) NOT NULL,
  user_id BIGINT NULL,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  citation_titles_json JSON NULL,
  citation_article_ids_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_rag_turn_session_user_created (session_id, user_id, created_at),
  KEY idx_rag_turn_created (created_at)
);

CREATE TABLE rag_conversation_summary (
  id BIGINT NOT NULL AUTO_INCREMENT,
  session_id VARCHAR(128) NOT NULL,
  user_key VARCHAR(64) NOT NULL,
  user_id BIGINT NULL,
  summary_text TEXT NOT NULL,
  turn_count INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_rag_summary_session_user (session_id, user_key),
  KEY idx_rag_summary_user_updated (user_id, updated_at)
);
