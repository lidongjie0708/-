import unittest

from app.agents.analytics_agent import metric_diagnostic_keys
from app.ops_metrics import diagnose_metric_rows, run_metric_diagnostics
from app.ops_metrics.registry import METRIC_DEFINITIONS
from app.tools.sql_tool import sql_safety_check_tool


class OperationsMetricDiagnosticsTests(unittest.TestCase):
    def test_registry_contains_versioned_governed_metrics(self) -> None:
        self.assertEqual({"engagement_rate", "content_supply", "negative_comment_rate"}, set(METRIC_DEFINITIONS))
        for definition in METRIC_DEFINITIONS.values():
            self.assertEqual("v1", definition.version)
            self.assertTrue(sql_safety_check_tool(definition.comparison_sql())["safe"])

    def test_significant_decline_contains_structured_evidence(self) -> None:
        diagnosis = diagnose_metric_rows(
            "engagement_rate",
            [
                {"period": "current", "metric_value": 4.0, "sample_size": 60},
                {"period": "baseline", "metric_value": 6.0, "sample_size": 90},
            ],
        )
        self.assertEqual("SIGNIFICANT_DECLINE", diagnosis["status"])
        self.assertEqual("v1", diagnosis["metricVersion"])
        self.assertEqual(-0.3333, diagnosis["evidence"]["relativeChange"])
        self.assertGreater(diagnosis["confidence"], 0.0)
        self.assertTrue(diagnosis["limitations"])

    def test_insufficient_sample_rejects_operational_conclusion(self) -> None:
        diagnosis = diagnose_metric_rows(
            "negative_comment_rate",
            [
                {"period": "current", "metric_value": 0.3, "sample_size": 8},
                {"period": "baseline", "metric_value": 0.1, "sample_size": 40},
            ],
        )
        self.assertEqual("INSUFFICIENT_DATA", diagnosis["status"])
        self.assertIsNone(diagnosis["finding"])
        self.assertEqual(0.0, diagnosis["confidence"])

    def test_runner_receives_only_governed_readonly_template(self) -> None:
        seen_sql = []

        def runner(sql: str) -> dict:
            seen_sql.append(sql)
            return {
                "ok": True,
                "kind": "query_result",
                "data": [
                    {"period": "current", "metric_value": 12, "sample_size": 40},
                    {"period": "baseline", "metric_value": 10, "sample_size": 60},
                ],
            }

        diagnoses = run_metric_diagnostics(["content_supply"], runner)
        self.assertEqual("NO_SIGNIFICANT_DECLINE", diagnoses[0]["status"])
        self.assertEqual(1, len(seen_sql))
        self.assertTrue(sql_safety_check_tool(seen_sql[0])["safe"])

    def test_stable_daily_content_supply_is_not_an_alert(self) -> None:
        # 70 posts in seven days and 560 posts in 56 days are both 10/day.
        diagnosis = diagnose_metric_rows(
            "content_supply",
            [
                {"period": "current", "metric_value": 10, "sample_size": 70},
                {"period": "baseline", "metric_value": 10, "sample_size": 560},
            ],
            current_window_days=7,
            baseline_window_days=56,
        )
        self.assertEqual("NO_SIGNIFICANT_DECLINE", diagnosis["status"])
        self.assertEqual(7, diagnosis["evidence"]["currentWindowDays"])
        self.assertEqual(56, diagnosis["evidence"]["baselineWindowDays"])
        self.assertEqual(10.0, diagnosis["evidence"]["currentNormalized"])

    def test_diagnostic_selection_requires_comparison_language(self) -> None:
        self.assertEqual([], metric_diagnostic_keys("show recent content"))
        self.assertEqual(["engagement_rate"], metric_diagnostic_keys("why did engagement decline?"))
        self.assertEqual(
            ["engagement_rate", "content_supply", "negative_comment_rate"],
            metric_diagnostic_keys("detect an anomaly"),
        )


if __name__ == "__main__":
    unittest.main()
