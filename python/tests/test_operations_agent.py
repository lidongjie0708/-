import unittest
from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.agents.operations_agent import analyze_operations
from app.api.routes import verify_agent_token
from app.infra.auth import AgentPrincipal
from app.main import app
from app.tools.operations_metrics_tool import content_engagement_sql
from app.tools.sql_tool import sql_safety_check_tool


def _rows(current_values, baseline_values, sample_size=40):
    today = date.today()
    rows = []
    for offset, value in enumerate(current_values):
        rows.append({"day": str(today - timedelta(days=offset)), "metric_value": value, "flagged_rate": value, "published_count": value, "sample_size": sample_size})
    for offset, value in enumerate(baseline_values, start=8):
        rows.append({"day": str(today - timedelta(days=offset)), "metric_value": value, "flagged_rate": value, "published_count": value, "sample_size": sample_size})
    return rows


class OperationsAgentTests(unittest.TestCase):
    def test_all_findings_have_evidence_and_deterministic_alerts(self):
        engagement = _rows([1, 1], [5, 7, 5, 7])
        risk = _rows([0.9, 0.8], [0.1, 0.2, 0.1, 0.2])
        supply = _rows([1, 1], [5, 7, 5, 7])
        responses = iter([{"ok": True, "data": engagement}, {"ok": True, "data": risk}, {"ok": True, "data": supply}])
        result = analyze_operations(current_days=7, baseline_days=30, query_runner=lambda _: next(responses))
        self.assertEqual(["OPEN", "OPEN", "OPEN"], [item["status"] for item in result["findings"]])
        for finding in result["findings"]:
            self.assertIn("anomalyScore", finding["evidence"])
            self.assertEqual("v1", finding["metric"]["version"])

    def test_insufficient_data_never_creates_anomaly_conclusion(self):
        rows = _rows([1], [3, 4], sample_size=5)
        result = analyze_operations(current_days=7, baseline_days=30, query_runner=lambda _: {"ok": True, "data": rows})
        self.assertEqual(["INSUFFICIENT_DATA"] * 3, [item["status"] for item in result["findings"]])
        self.assertEqual(0.0, result["findings"][0]["confidence"])

    def test_template_is_readonly_and_tag_is_constrained(self):
        self.assertTrue(sql_safety_check_tool(content_engagement_sql(63, "java"))["safe"])


class OperationsRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides.clear()

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_endpoint_requires_admin(self):
        app.dependency_overrides[verify_agent_token] = lambda: AgentPrincipal("u", 1, "USER", "agent:stream")
        response = self.client.post("/api/agent/operations/analyze", json={})
        self.assertEqual(200, response.status_code)
        self.assertEqual("NO_PERMISSION", response.json()["error"])

    def test_admin_endpoint_returns_analysis(self):
        app.dependency_overrides[verify_agent_token] = lambda: AgentPrincipal("a", 1, "ADMIN", "agent:stream")
        with patch("app.api.routes.analyze_operations", return_value={"status": "SUCCESS", "findings": []}):
            response = self.client.post("/api/agent/operations/analyze", json={"currentDays": 7, "baselineDays": 30})
        self.assertEqual(0, response.json()["code"])
        self.assertEqual("SUCCESS", response.json()["data"]["status"])


if __name__ == "__main__":
    unittest.main()
