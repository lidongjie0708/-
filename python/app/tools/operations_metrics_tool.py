"""Application-owned, read-only queries for the operations analysis endpoint.

The agent never receives a database tool.  These templates are deliberately
small and deterministic so an operator can reproduce every finding.
"""
from __future__ import annotations

from typing import Any

from app.tools.sql_tool import safe_readonly_sql_query


def _tag_predicate(tag: str | None) -> str:
    if not tag:
        return ""
    # The request model permits only a conservative tag character set. Escape
    # the remaining SQL quote defensively to keep this template application-owned.
    escaped = tag.replace("'", "''")
    return f" AND FIND_IN_SET('{escaped}', tags) > 0"


def content_engagement_sql(window_days: int, tag: str | None = None) -> str:
    return (
        "SELECT DATE(createTime) AS day, "
        "COALESCE(SUM(thumbCount), 0) / NULLIF(COUNT(id), 0) AS metric_value, COUNT(id) AS sample_size "
        "FROM blog WHERE audit_status = 1"
        f"{_tag_predicate(tag)} AND createTime >= DATE_SUB(CURDATE(), INTERVAL {window_days} DAY) "
        "GROUP BY DATE(createTime) ORDER BY DATE(createTime) ASC LIMIT 100"
    )


def comment_risk_sql(window_days: int) -> str:
    return (
        "SELECT DATE(created_at) AS day, "
        "COALESCE(SUM(CASE WHEN is_flagged = 1 THEN 1 ELSE 0 END), 0) / NULLIF(COUNT(id), 0) AS flagged_rate, "
        "AVG(sentiment_score) AS avg_sentiment, COUNT(id) AS sample_size "
        "FROM comments WHERE is_deleted = 0 "
        f"AND created_at >= DATE_SUB(CURDATE(), INTERVAL {window_days} DAY) "
        "GROUP BY DATE(created_at) ORDER BY DATE(created_at) ASC LIMIT 100"
    )


def content_supply_sql(window_days: int, tag: str | None = None) -> str:
    return (
        "SELECT DATE(createTime) AS day, COUNT(id) AS published_count, COUNT(DISTINCT userId) AS active_authors "
        "FROM blog WHERE audit_status = 1"
        f"{_tag_predicate(tag)} AND createTime >= DATE_SUB(CURDATE(), INTERVAL {window_days} DAY) "
        "GROUP BY DATE(createTime) ORDER BY DATE(createTime) ASC LIMIT 100"
    )


def run_operations_metric(query: str) -> dict[str, Any]:
    """Only bridge to the existing guarded read-only SQL executor."""
    return safe_readonly_sql_query(query)
