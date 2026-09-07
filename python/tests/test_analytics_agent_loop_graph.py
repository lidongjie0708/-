import unittest
from unittest.mock import patch

from app.agents import analytics_agent
from app.tools import sql_tool


class Response:
    def __init__(self, calls=None, content=""):
        self.tool_calls = calls or []
        self.content = content


class Model:
    def __init__(self, responses):
        self.responses = list(responses)

    def bind_tools(self, _tools):
        return self

    def invoke(self, _messages):
        return self.responses.pop(0)


def state():
    return {
        "question": "custom analysis", "role": "ADMIN", "user_id": 1,
        "analysis_spec": {}, "analysis_plan": {},
        "execution_plan": analytics_agent.new_execution_plan("custom analysis"),
    }


class AgentLoopGraphTests(unittest.TestCase):
    def test_routes_template_and_agent_loop(self):
        self.assertEqual("template", analytics_agent.route_after_analysis_plan({"use_template_path": True}))
        self.assertEqual("agent_loop", analytics_agent.route_after_analysis_plan({"use_template_path": False}))

    def test_composite_tool_rejects_without_database_call(self):
        with patch.object(sql_tool, "execute_readonly_sql") as execute:
            result = sql_tool.safe_readonly_sql_query("DELETE FROM blog LIMIT 1")
        self.assertFalse(result["ok"])
        self.assertEqual("safety_rejected", result["kind"])
        execute.assert_not_called()

    def test_repeated_sql_is_executed_once_and_finalized(self):
        sql = "SELECT id, title FROM blog ORDER BY createTime DESC LIMIT 5"
        model = Model([
            Response([{"id": "one", "name": "safe_readonly_sql_query", "args": {"sql": sql}}]),
            Response([{"id": "two", "name": "safe_readonly_sql_query", "args": {"sql": sql}}]),
            Response(content='{"done": true}'),
        ])
        result = {"ok": True, "kind": "query_result", "sql": sql, "rowCount": 1, "data": [{"id": 1}], "safety": {"safe": True}}
        with patch.object(analytics_agent, "llm_factory", return_value=model), patch.object(analytics_agent, "get_safe_analytics_tools", return_value=[object()]), patch.object(analytics_agent, "safe_readonly_sql_query", return_value=result) as execute:
            current = analytics_agent.agent_loop_init_node(state())
            for _ in range(2):
                current = analytics_agent.agent_decide_node(current)
                current = analytics_agent.safe_query_executor_node(current)
            current = analytics_agent.agent_decide_node(current)
            current = analytics_agent.finalize_agent_loop_node(current)
        self.assertEqual(1, execute.call_count)
        self.assertEqual(1, len(current["query_results"]))
        self.assertEqual("agent_loop", current["sql_source"])

    def test_invalid_model_termination_is_blocked(self):
        with patch.object(analytics_agent, "llm_factory", return_value=Model([Response(content="not done")])), patch.object(analytics_agent, "get_safe_analytics_tools", return_value=[object()]):
            current = analytics_agent.agent_decide_node(analytics_agent.agent_loop_init_node(state()))
        self.assertEqual("blocked", analytics_agent.route_after_agent_decide(current))
        self.assertEqual("invalid_model_termination", current["loop_stop_reason"])

    def test_round_budget_requires_done(self):
        current = analytics_agent.agent_loop_init_node(state())
        current["loop_round"] = analytics_agent.settings.analytics_max_tool_rounds
        current = analytics_agent.agent_decide_node(current)
        self.assertEqual("max_tool_rounds_reached", current["loop_stop_reason"])
        self.assertEqual("blocked", analytics_agent.route_after_agent_decide(current))


if __name__ == "__main__":
    unittest.main()
