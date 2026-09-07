import unittest
from unittest.mock import patch

from app.agents import analytics_agent


class FakeGraph:
    """Minimal stand-in for a compiled LangGraph that streams updates."""

    def __init__(self, updates):
        self.updates = updates

    def stream(self, state, stream_mode="updates"):
        for update in self.updates:
            yield update


def fake_state(**overrides):
    state = {
        "question": "热门内容怎么样",
        "role": "ADMIN",
        "user_id": 1,
        "session_id": None,
        "forced_intent": None,
        "status": "RUNNING",
        "error": None,
        "execution_plan": analytics_agent.new_execution_plan("热门内容怎么样"),
        "data": [],
        "sql_list": [],
        "query_results": [],
        "safety_results": [],
        "memory": {"enabled": False, "long_term": [], "short_turns": [], "sessionMemory": []},
    }
    state.update(overrides)
    return state


def template_path_updates():
    """Simulate the template path: permission -> intent -> supervisor -> sql -> report."""
    return [
        {"permission": fake_state()},
        {
            "intent": fake_state(
                intent="HOT_ARTICLE",
                intent_confidence=0.9,
                use_template_path=True,
                analysis_spec={"intent": "HOT_ARTICLE", "limit": 10, "filters": {}, "metrics": [], "dimension": "article"},
            )
        },
        {
            "supervisor": fake_state(
                intent="HOT_ARTICLE",
                supervisor={"declaration": "我将查询：热门内容 TOP 10（按点赞数排序）", "route": "data_qa_template"},
            )
        },
        {
            "template_sql_generation": fake_state(
                sql="SELECT id, title, thumbCount FROM blog ORDER BY thumbCount DESC LIMIT 10",
                sql_list=["SELECT id, title, thumbCount FROM blog ORDER BY thumbCount DESC LIMIT 10"],
                sql_source="template",
                execution_mode="template",
            )
        },
        {"safety_tool": fake_state(safety={"safe": True}, safety_results=[{"safe": True, "sql": "SELECT 1"}])},
        {
            "sql_tool": fake_state(
                query_results=[
                    {
                        "index": 0,
                        "sql": "SELECT id, title, thumbCount FROM blog ORDER BY thumbCount DESC LIMIT 10",
                        "rowCount": 2,
                        "data": [{"title": "a", "thumbCount": 5}, {"title": "b", "thumbCount": 3}],
                    }
                ],
                data=[{"title": "a", "thumbCount": 5}, {"title": "b", "thumbCount": 3}],
            )
        },
        {
            "report": fake_state(
                status="SUCCESS",
                report={"summary": "点赞最高的文章是《a》", "insights": [], "suggestions": []},
                chart={"type": "bar", "xField": "title", "yField": "thumbCount", "data": []},
                query_results=[
                    {
                        "index": 0,
                        "sql": "SELECT id, title, thumbCount FROM blog ORDER BY thumbCount DESC LIMIT 10",
                        "rowCount": 2,
                        "data": [{"title": "a", "thumbCount": 5}],
                    }
                ],
                data=[{"title": "a", "thumbCount": 5}],
            )
        },
    ]


class AnalyticsStreamEventTests(unittest.TestCase):
    def test_node_events_emit_status_plan_sql_in_order(self):
        emitted = {"plan": False, "sqls": set()}
        events = list(
            analytics_agent._iter_node_events(
                "sql_tool",
                fake_state(
                    supervisor={"declaration": "我将查询：热门内容 TOP 10"},
                    query_results=[{"index": 0, "sql": "SELECT 1 LIMIT 1", "rowCount": 3}],
                ),
                emitted,
            )
        )
        kinds = [kind for kind, _ in events]
        self.assertEqual(kinds, ["status", "plan", "sql"])
        payloads = {kind: payload for kind, payload in events}
        self.assertEqual("正在执行查询…", payloads["status"]["message"])
        self.assertEqual("我将查询：热门内容 TOP 10", payloads["plan"]["declaration"])
        self.assertEqual(3, payloads["sql"]["rowCount"])

    def test_plan_emitted_only_once(self):
        emitted = {"plan": False, "sqls": set()}
        update = fake_state(supervisor={"declaration": "我将查询：概览"})
        list(analytics_agent._iter_node_events("supervisor", update, emitted))
        later = list(analytics_agent._iter_node_events("report", update, emitted))
        self.assertFalse(any(kind == "plan" for kind, _ in later))

    def test_sql_events_deduplicated_across_nodes(self):
        emitted = {"plan": True, "sqls": set()}
        update = fake_state(
            query_results=[{"index": 0, "sql": "SELECT 1 LIMIT 1", "rowCount": 1}]
        )
        first = list(analytics_agent._iter_node_events("sql_tool", update, emitted))
        second = list(analytics_agent._iter_node_events("report", update, emitted))
        self.assertEqual(1, sum(1 for kind, _ in first if kind == "sql"))
        self.assertFalse(any(kind == "sql" for kind, _ in second))

    def test_agent_loop_results_emit_sql_with_row_count(self):
        update = fake_state(
            loop_query_results=[
                {"ok": True, "sql": "SELECT COUNT(*) AS c FROM blog LIMIT 1", "rowCount": 1, "data": [{"c": 7}]},
                {"ok": False, "sql": "SELECT BAD", "rowCount": 0, "error": "rejected"},
            ]
        )
        sqls = list(analytics_agent._extract_executed_sqls(update))
        self.assertEqual([("SELECT COUNT(*) AS c FROM blog LIMIT 1", 1)], sqls)

    def test_stream_yields_progress_events_then_result(self):
        with (
            patch.object(analytics_agent, "build_analytics_graph", return_value=FakeGraph(template_path_updates())),
            patch.object(
                analytics_agent,
                "_load_memory_context",
                return_value={"enabled": False, "long_term": [], "short_turns": [], "sessionMemory": []},
            ),
            patch.object(analytics_agent, "_save_analysis_log"),
            patch.object(analytics_agent, "_remember_turn"),
        ):
            events = list(analytics_agent.stream_analyze_operation("热门内容怎么样", "ADMIN", 1))

        kinds = [kind for kind, _ in events]
        self.assertEqual("result", kinds[-1])
        self.assertIn("status", kinds)
        self.assertIn("plan", kinds)
        self.assertEqual(1, kinds.count("sql"))
        result = events[-1][1]
        self.assertEqual("SUCCESS", result["status"])
        self.assertEqual("我将查询：热门内容 TOP 10（按点赞数排序）", result["declaration"])
        self.assertEqual(["SELECT id, title, thumbCount FROM blog ORDER BY thumbCount DESC LIMIT 10"], result["sqlList"])

    def test_analyze_operation_returns_same_result_as_stream(self):
        with (
            patch.object(analytics_agent, "build_analytics_graph", return_value=FakeGraph(template_path_updates())),
            patch.object(
                analytics_agent,
                "_load_memory_context",
                return_value={"enabled": False, "long_term": [], "short_turns": [], "sessionMemory": []},
            ),
            patch.object(analytics_agent, "_save_analysis_log"),
            patch.object(analytics_agent, "_remember_turn"),
        ):
            streamed = list(analytics_agent.stream_analyze_operation("热门内容怎么样", "ADMIN", 1))
            direct = analytics_agent.analyze_operation("热门内容怎么样", "ADMIN", 1)
        self.assertEqual(streamed[-1][1], direct)


if __name__ == "__main__":
    unittest.main()
