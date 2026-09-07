from __future__ import annotations

from typing import Any, Callable

from .registry import MetricDefinition, get_metric_definition


QueryRunner = Callable[[str], dict[str, Any]]


def diagnose_metric_rows(
    metric_key: str, rows: list[dict[str, Any]], current_window_days: int = 7, baseline_window_days: int = 56
) -> dict[str, Any]:
    """Create a deterministic, evidence-backed diagnosis from two aggregate rows."""
    definition = get_metric_definition(metric_key)
    if not definition:
        return _rejected(metric_key, "METRIC_NOT_DEFINED", "The requested metric is not in the governed registry.")
    periods = {str(row.get("period", "")).lower(): row for row in rows}
    current, baseline = periods.get("current"), periods.get("baseline")
    if not current or not baseline:
        return _rejected(
            metric_key, "INCOMPLETE_COMPARISON", "Current and baseline observations are both required.", definition
        )
    try:
        current_value, baseline_value = float(current["metric_value"]), float(baseline["metric_value"])
        current_n, baseline_n = int(current["sample_size"]), int(baseline["sample_size"])
    except (KeyError, TypeError, ValueError):
        return _rejected(
            metric_key, "INVALID_METRIC_DATA", "Metric rows must contain numeric value and sample size.", definition
        )

    evidence = {
        "metric": metric_key,
        "metricVersion": definition.version,
        "current": current_value,
        "baseline": baseline_value,
        "currentSampleSize": current_n,
        "baselineSampleSize": baseline_n,
        "minimumRequired": definition.minimum_sample_size,
        "currentWindowDays": current_window_days,
        "baselineWindowDays": baseline_window_days,
        "currentNormalized": current_value,
        "baselineNormalized": baseline_value,
    }
    if min(current_n, baseline_n) < definition.minimum_sample_size:
        return {
            "status": "INSUFFICIENT_DATA",
            "metric": metric_key,
            "metricVersion": definition.version,
            "finding": None,
            "confidence": 0.0,
            "evidence": evidence,
            "limitations": [
                "Sample size is below the metric definition minimum; no operational conclusion was generated."
            ],
        }

    relative_change = (current_value - baseline_value) / max(abs(baseline_value), 1e-9)
    # The practical effect guard prevents calling noise a regression. The sample
    # guard above and this fixed, auditable threshold make the rule reproducible.
    is_downturn = relative_change <= -0.20
    confidence = min(0.95, 0.55 + min(current_n, baseline_n) / (definition.minimum_sample_size * 10))
    evidence["relativeChange"] = round(relative_change, 4)
    if is_downturn:
        finding = f"{definition.display_name} declined {abs(relative_change):.1%} versus the historical baseline."
        status = "SIGNIFICANT_DECLINE"
    else:
        finding = (
            f"No significant decline detected for {definition.display_name}; "
            f"change versus baseline is {relative_change:.1%}."
        )
        status = "NO_SIGNIFICANT_DECLINE"
    return {
        "status": status,
        "metric": metric_key,
        "metricVersion": definition.version,
        "finding": finding,
        "confidence": round(confidence, 2),
        "evidence": evidence,
        "limitations": [definition.description, "Comparison is descriptive and does not establish causality."],
    }


def run_metric_diagnostics(
    metric_keys: list[str], query_runner: QueryRunner, current_days: int = 7, baseline_days: int = 56
) -> list[dict[str, Any]]:
    """Execute governed templates through an injected safe read-only runner."""
    diagnoses: list[dict[str, Any]] = []
    for metric_key in dict.fromkeys(metric_keys):
        definition = get_metric_definition(metric_key)
        if not definition:
            diagnoses.append(
                _rejected(metric_key, "METRIC_NOT_DEFINED", "The requested metric is not in the governed registry.")
            )
            continue
        response = query_runner(definition.comparison_sql(current_days, baseline_days))
        if not response.get("ok") or response.get("kind") != "query_result":
            diagnoses.append(
                _rejected(
                    metric_key,
                    "QUERY_FAILED",
                    "The governed read-only comparison query did not return data.",
                    definition,
                )
            )
            continue
        diagnoses.append(diagnose_metric_rows(metric_key, response.get("data") or [], current_days, baseline_days))
    return diagnoses


def _rejected(
    metric_key: str, code: str, limitation: str, definition: MetricDefinition | None = None
) -> dict[str, Any]:
    return {
        "status": code,
        "metric": metric_key,
        "metricVersion": definition.version if definition else None,
        "finding": None,
        "confidence": 0.0,
        "evidence": {},
        "limitations": [limitation],
    }
