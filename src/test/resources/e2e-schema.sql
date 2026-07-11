CREATE TABLE user (
  id BIGINT NOT NULL AUTO_INCREMENT,
  username VARCHAR(50) NOT NULL,
  password VARCHAR(255) NOT NULL,
  email VARCHAR(100),
  full_name VARCHAR(100),
  enabled TINYINT DEFAULT 1,
  role VARCHAR(20) NOT NULL DEFAULT 'USER',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_username (username)
);

CREATE TABLE blog (
  id BIGINT NOT NULL AUTO_INCREMENT,
  userId BIGINT NOT NULL,
  title VARCHAR(512),
  coverImg VARCHAR(1024),
  content TEXT NOT NULL,
  content_format VARCHAR(16) NOT NULL DEFAULT 'PLAIN',
  thumbCount INT NOT NULL DEFAULT 0,
  summary VARCHAR(500),
  tags VARCHAR(200),
  embedding_status TINYINT DEFAULT 0,
  audit_status TINYINT DEFAULT 0,
  createTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updateTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_userId (userId)
);

CREATE TABLE comments (
  id BIGINT NOT NULL AUTO_INCREMENT,
  blog_id VARCHAR(50) NOT NULL,
  user_id BIGINT NOT NULL,
  content TEXT NOT NULL,
  sentiment_score INT,
  is_flagged TINYINT DEFAULT 0,
  parent_id BIGINT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  is_deleted TINYINT DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_blog_id (blog_id),
  KEY idx_parent_id (parent_id)
);

CREATE TABLE thumb (
  id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  blog_id BIGINT NOT NULL,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_blog (user_id, blog_id)
);

CREATE TABLE rag_eval_log (
  id BIGINT NOT NULL AUTO_INCREMENT,
  question VARCHAR(1000) NOT NULL,
  answer LONGTEXT,
  user_id BIGINT,
  role VARCHAR(50),
  confidence DOUBLE,
  citation_count INT DEFAULT 0,
  context_precision_lite DOUBLE,
  answer_grounding_lite DOUBLE,
  has_citations TINYINT DEFAULT 0,
  keyword_hit_rate DOUBLE,
  query_rewrite_json JSON,
  citations_json JSON,
  evaluation_json JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
);

CREATE TABLE agent_analysis_log (
  id BIGINT NOT NULL AUTO_INCREMENT,
  question VARCHAR(1000) NOT NULL,
  intent VARCHAR(80),
  user_id BIGINT,
  role VARCHAR(50),
  sql_text LONGTEXT,
  status VARCHAR(30) NOT NULL,
  row_count INT DEFAULT 0,
  confidence DOUBLE,
  chart_json JSON,
  result_json JSON,
  insight LONGTEXT,
  suggestions_json JSON,
  plan_json JSON,
  error_message VARCHAR(1000),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
);

CREATE TABLE outbox_event (
  id BIGINT NOT NULL,
  event_type VARCHAR(100) NOT NULL,
  aggregate_type VARCHAR(50) NOT NULL,
  aggregate_id VARCHAR(100) NOT NULL,
  exchange_name VARCHAR(120) NOT NULL,
  routing_key VARCHAR(120) NOT NULL,
  payload JSON NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'NEW',
  retry_count INT NOT NULL DEFAULT 0,
  next_retry_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_error VARCHAR(1000),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_outbox_status_retry (status, next_retry_time),
  KEY idx_outbox_aggregate (aggregate_type, aggregate_id)
);
