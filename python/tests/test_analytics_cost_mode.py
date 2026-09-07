import unittest

from app.agents import analytics_agent


class AnalyticsCostModeTests(unittest.TestCase):
    def test_template_intent_skips_llm_classification(self) -> None:
        payload = analytics_agent.detect_intent("top liked articles")

        self.assertEqual("HOT_ARTICLE", payload["intent"])
        self.assertTrue(payload["llmSkipped"])
        self.assertGreaterEqual(payload["confidence"], analytics_agent.TEMPLATE_CONFIDENCE_THRESHOLD)

    def test_template_plan_uses_local_fallback(self) -> None:
        state = {
            "question": "top liked articles",
            "intent": "HOT_ARTICLE",
            "intent_confidence": 0.82,
            "execution_plan": analytics_agent.new_execution_plan("top liked articles"),
        }

        result = analytics_agent.analysis_plan_node(state)

        self.assertEqual("HOT_ARTICLE", result["analysis_plan"]["intent"])
        self.assertEqual("SKIPPED", result["execution_plan"]["steps"][-1]["status"])

    def test_template_report_uses_fallback_without_llm(self) -> None:
        report = analytics_agent.generate_report(
            "top liked articles",
            "HOT_ARTICLE",
            "SELECT id, title FROM blog LIMIT 10",
            [{"id": 1, "title": "Redis notes", "thumbCount": 9}],
            [{"index": 0, "sql": "SELECT id, title FROM blog LIMIT 10", "rowCount": 1, "data": []}],
            {"intent": "HOT_ARTICLE"},
            "template",
        )

        self.assertIn("点赞最高", report["summary"])
        self.assertIn("Redis notes", report["summary"])
        self.assertEqual("write_followup", report["suggestions"][0]["action"])


if __name__ == "__main__":
    unittest.main()
