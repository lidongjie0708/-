"""Evidence-first operations analysis; no free-form SQL and no persistence."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import sqrt
from typing import Any, Callable

from app.tools.operations_metrics_tool import (
    comment_risk_sql,
    content_engagement_sql,
    content_supply_sql,
    run_operations_metric,
)

QueryRunner = Callable[[str], dict[str, Any]]
MINIMUM_SAMPLE = 30
Z_THRESHOLD = 2.0


def analyze_operations(
    *, current_days: int = 7, baseline_days: int = 56, tag: str | None = None, query_runner: QueryRunner = run_operations_metric
) -> dict[str, Any]:
    """Run the three governed finding templates and return auditable evidence."""
    if not 1 <= current_days < baseline_days <= 90:
        raise ValueError("windows must satisfy 1 <= currentDays < baselineDays <= 90")
    # SQL's DATE_SUB boundary is inclusive.  Request one fewer day so the
    # returned series contains exactly ``current_days + baseline_days`` dates
    # when today's partial day is included in the current window.
    total_days = current_days + baseline_days - 1
    definitions = (
        ("CONTENT_ENGAGEMENT_DROP", "engagement_rate", content_engagement_sql(total_days, tag), "metric_value"),
        ("COMMENT_RISK_SPIKE", "flagged_comment_rate", comment_risk_sql(total_days), "flagged_rate"),
        ("CONTENT_SUPPLY_GAP", "published_content_count", content_supply_sql(total_days, tag), "published_count"),
    )
    findings = []
    for finding_type, metric_key, sql, value_key in definitions:
        response = query_runner(sql)
        rows = response.get("data") if response.get("ok") else []
        findings.append(_build_finding(finding_type, metric_key, value_key, rows or [], current_days, baseline_days, tag, response))
    return {
        "status": "SUCCESS",
        "metricVersions": {"engagement_rate": "v1", "flagged_comment_rate": "v1", "published_content_count": "v1"},
        "findings": findings,
        "dataFreshAt": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Findings are descriptive comparisons and do not establish causality.", "No exposure data is used; CTR is not inferred."],
    }


def _build_finding(
    finding_type: str, metric_key: str, value_key: str, rows: list[dict[str, Any]], current_days: int,
    baseline_days: int, tag: str | None, response: dict[str, Any],
) -> dict[str, Any]:
    current, baseline = _split_windows(rows, current_days)
    current_samples = sum(_number(row.get("sample_size")) for row in current)
    baseline_samples = sum(_number(row.get("sample_size")) for row in baseline)
    evidence: dict[str, Any] = {
        "metricKey": metric_key, "metricVersion": "v1", "currentWindowDays": current_days,
        "baselineWindowDays": baseline_days, "currentSampleSize": int(current_samples),
        "baselineSampleSize": int(baseline_samples), "minimumSampleSize": MINIMUM_SAMPLE,
        "queryTemplate": finding_type, "queryAccepted": bool(response.get("ok")),
    }
    if tag:
        evidence["tag"] = tag
    if not response.get("ok"):
        return _insufficient(finding_type, metric_key, evidence, ["Governed read-only query failed; no conclusion was generated."])
    if current_samples < MINIMUM_SAMPLE or baseline_samples < MINIMUM_SAMPLE or not current or len(baseline) < 2:
        return _insufficient(finding_type, metric_key, evidence, ["Current or baseline sample is below the governed minimum, or the baseline has fewer than two daily observations."])
    current_value = _weighted_mean(current, value_key)
    baseline_values = [_number(row.get(value_key)) for row in baseline]
    baseline_mean = sum(baseline_values) / len(baseline_values)
    baseline_stddev = _stddev(baseline_values)
    evidence.update({"currentValue": round(current_value, 6), "baselineMean": round(baseline_mean, 6), "baselineStdDev": round(baseline_stddev, 6)})
    if baseline_stddev == 0:
        return _insufficient(finding_type, metric_key, evidence, ["Baseline standard deviation is zero; an anomaly score would be misleading."])
    z_score = (current_value - baseline_mean) / baseline_stddev
    evidence["anomalyScore"] = round(z_score, 4)
    is_alert = z_score <= -Z_THRESHOLD if finding_type != "COMMENT_RISK_SPIKE" else z_score >= Z_THRESHOLD
    status = "OPEN" if is_alert else "NO_ANOMALY"
    limitations = ["Comment samples expose IDs only in downstream review, never comment body text."] if finding_type == "COMMENT_RISK_SPIKE" else ["No exposure data is available, so this is not a CTR diagnosis."]
    return {
        "type": finding_type, "status": status, "target": {"type": "TAG" if tag else "PLATFORM", "id": tag or "all"},
        "metric": {"key": metric_key, "version": "v1"}, "evidence": evidence,
        "confidence": round(min(0.95, 0.55 + min(current_samples, baseline_samples) / 600), 2), "limitations": limitations,
    }


def _insufficient(finding_type: str, metric_key: str, evidence: dict[str, Any], limitations: list[str]) -> dict[str, Any]:
    return {"type": finding_type, "status": "INSUFFICIENT_DATA", "metric": {"key": metric_key, "version": "v1"}, "evidence": evidence, "confidence": 0.0, "limitations": limitations}


def _split_windows(rows: list[dict[str, Any]], current_days: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # A seven-day window means today and the preceding six calendar days, not
    # eight days.  Keep this aligned with the inclusive SQL date predicate.
    cutoff = date.today() - timedelta(days=current_days - 1)
    current, baseline = [], []
    for row in rows:
        parsed = _parse_day(row.get("day"))
        if parsed is None:
            continue
        (current if parsed >= cutoff else baseline).append(row)
    return current, baseline


def _parse_day(value: Any) -> date | None:
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    try: return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError): return None


def _number(value: Any) -> float:
    try: return float(value or 0)
    except (TypeError, ValueError): return 0.0


def _weighted_mean(rows: list[dict[str, Any]], key: str) -> float:
    weights = [_number(row.get("sample_size")) for row in rows]
    return sum(_number(row.get(key)) * weight for row, weight in zip(rows, weights)) / max(sum(weights), 1.0)


def _stddev(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / len(values))
