from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinition:
    """A governed metric. SQL is deliberately kept in application-owned templates."""

    key: str
    version: str
    display_name: str
    description: str
    minimum_sample_size: int
    source_table: str
    time_column: str
    value_expression: str
    base_predicate: str
    normalize_by_window_days: bool = False

    def comparison_sql(self, current_days: int = 7, baseline_days: int = 56) -> str:
        """Return a single bounded, read-only current-vs-baseline query.

        The caller must still use ``safe_readonly_sql_query``; this module does
        not provide a database bypass.
        """
        if not 1 <= current_days < baseline_days <= 365:
            raise ValueError("comparison windows must satisfy 1 <= current < baseline <= 365")
        # Keep this to one SELECT because the existing SQL guard deliberately
        # accepts only a Select AST (not a UNION). The CASE produces the same
        # two observations without expanding that safety boundary.
        period = (
            f"CASE WHEN {self.time_column} >= DATE_SUB(NOW(), INTERVAL {current_days} DAY) "
            "THEN 'current' ELSE 'baseline' END"
        )
        metric_value = self.value_expression
        if self.normalize_by_window_days:
            window_days = (
                f"CASE WHEN {self.time_column} >= DATE_SUB(NOW(), INTERVAL {current_days} DAY) "
                f"THEN {current_days} ELSE {baseline_days} END"
            )
            metric_value = f"({metric_value}) / NULLIF({window_days}, 0)"
        return (
            f"SELECT {period} AS period, {metric_value} AS metric_value, COUNT(*) AS sample_size "
            f"FROM {self.source_table} WHERE {self.base_predicate} "
            f"AND {self.time_column} >= DATE_SUB(NOW(), INTERVAL {baseline_days} DAY) "
            f"GROUP BY {period} LIMIT 2"
        )


METRIC_DEFINITIONS: dict[str, MetricDefinition] = {
    "engagement_rate": MetricDefinition(
        key="engagement_rate",
        version="v1",
        display_name="Engagement rate",
        description="Average stored thumbs per published article. Exposure is not available in this schema.",
        minimum_sample_size=30,
        source_table="blog",
        time_column="createTime",
        value_expression="COALESCE(SUM(thumbCount), 0) / NULLIF(COUNT(*), 0)",
        base_predicate="audit_status = 1",
    ),
    "content_supply": MetricDefinition(
        key="content_supply",
        version="v1",
        display_name="Content supply",
        description="Published article count in the observation window.",
        minimum_sample_size=10,
        source_table="blog",
        time_column="createTime",
        value_expression="COUNT(*)",
        base_predicate="audit_status = 1",
        normalize_by_window_days=True,
    ),
    "negative_comment_rate": MetricDefinition(
        key="negative_comment_rate",
        version="v1",
        display_name="Negative comment rate",
        description="Share of non-deleted comments whose sentiment score is below zero.",
        minimum_sample_size=30,
        source_table="comments",
        time_column="created_at",
        value_expression="COALESCE(SUM(CASE WHEN sentiment_score < 0 THEN 1 ELSE 0 END), 0) / NULLIF(COUNT(*), 0)",
        base_predicate="is_deleted = 0",
    ),
}


def get_metric_definition(key: str) -> MetricDefinition | None:
    return METRIC_DEFINITIONS.get(key)
