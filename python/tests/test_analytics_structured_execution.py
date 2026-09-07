import unittest
from unittest.mock import patch

from app.agents import analytics_agent


class FakeResponse:
    def __init__(self, *, tool_calls=None, content="") -> None:
        self.tool_calls = tool_calls or []
        self.content = content


class FakeToolModel:
    def __init__(self, responses) -> None:
        self.responses = list(responses)

    def bind_tools(self, _tools):
        return self

    def invoke(self, _messages):
        return self.responses.pop(0)


class StructuredAnalyticsTests(unittest.TestCase):
    def test_limit_and_time_range_are_distinct_slots(self) -> None:
        question = "查询近 30 天点赞最高的 5 篇文章"
        spec = analytics_agent.normalize_analysis_spec({}, question, "HOT_ARTICLE")

        self.assertEqual(5, spec["limit"])
        self.assertEqual({"type": "relative_days", "value": 30}, spec["timeRange"])
        sql = analytics_agent.sql_from_template("HOT_ARTICLE", spec)
        self.assertIn("INTERVAL 30 DAY", sql)
        self.assertTrue(sql.endswith("LIMIT 5"))

    def test_template_is_rejected_for_unsupported_filter(self) -> None:
        spec = {
            "intent": "HOT_ARTICLE",
            "metrics": [],
            "dimension": "article",
            "filters": {"authorId": 7},
            "limit": 5,
        }
        self.assertFalse(analytics_agent.template_path_enabled(spec, 0.95))

    def test_complex_template_request_is_downgraded_to_llm_path(self) -> None:
        spec = analytics_agent.normalize_analysis_spec({}, "查询排除草稿的热门文章", "HOT_ARTICLE")
        self.assertIn("unsupportedRequirements", spec["filters"])
        self.assertFalse(analytics_agent.template_path_enabled(spec, 0.95))

    @unittest.skip("Legacy hidden Python tool loop was replaced by explicit graph-node tests.")
    def test_autonomous_loop_checks_then_executes_and_reuses_results(self) -> None:
        sql = "SELECT id, title FROM blog ORDER BY createTime DESC LIMIT 5"
        model = FakeToolModel(
            [
                FakeResponse(tool_calls=[{"id": "safe-1", "name": "sql_safety_check", "args": {"sql": sql}}]),
                FakeResponse(tool_calls=[{"id": "query-1", "name": "readonly_sql_query", "args": {"sql": sql}}]),
                FakeResponse(content='{"done": true}'),
            ]
        )
        state = {
            "question": "查看最近文章",
            "analysis_spec": {"intent": "CUSTOM_SQL", "limit": 5, "filters": {}},
            "analysis_plan": {"goal": "查看最近文章"},
        }
        with (
            patch.object(analytics_agent, "llm_factory", return_value=model),
            patch.object(analytics_agent, "get_admin_analytics_tools", return_value=[object(), object()]),
            patch.object(analytics_agent, "execute_readonly_sql", return_value=[{"id": 1, "title": "A"}]) as execute,
        ):
            loop = analytics_agent.run_autonomous_sql_tool_loop(state)

        self.assertEqual([sql], loop["sqlList"])
        self.assertTrue(loop["safetyResults"][0]["safe"])
        self.assertEqual(1, loop["queryResults"][0]["rowCount"])
        self.assertEqual(1, execute.call_count)


if __name__ == "__main__":
    unittest.main()
