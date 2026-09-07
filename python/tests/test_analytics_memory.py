import unittest
from unittest.mock import PropertyMock, patch

from app.agents import analytics_memory
from app.agents import analytics_agent


def _set_setting(name: str, value) -> None:
    object.__setattr__(analytics_agent.settings, name, value)


class AnalyticsMemoryTests(unittest.TestCase):
    def test_render_prompt_loads_files(self):
        for name in ("supervisor", "data_qa_agent", "anomaly_diagnosis_agent", "memory_consolidator"):
            text = analytics_memory.render_prompt(name)
            self.assertTrue(text.strip(), f"{name} prompt should be non-empty")

    def test_layered_context_includes_memory_and_reports_trim(self):
        layered = analytics_memory.build_layered_context(
            system_prompt="L0 system",
            long_term=[{"scope": "USER", "content": "用户关注评论风险"}],
            short_turns=[{"question": "热门内容", "intent": "HOT_ARTICLE", "rowCount": 10, "conclusion": "TOP 是 Redis"}],
            question="热门内容",
            analysis_spec={},
            analysis_plan={},
            l1_budget=100,
            l2_budget=100,
        )
        self.assertIn("L0 system", layered["system"])
        self.assertIn("long_memory", layered["user"])
        self.assertIn("short_memory", layered["user"])
        self.assertEqual([], layered["trimmed"])

    def test_compress_short_memory_keeps_recent(self):
        turns = [{"question": f"q{i}", "intent": "HOT_ARTICLE", "rowCount": i} for i in range(8)]
        result = analytics_memory.ops_memory.compress_short_memory(999, "compress-test")
        # No Redis data, so nothing to compress; pure function still returns structure.
        self.assertIn("turns", result)
        self.assertIn("compressed", result)

    def test_fallback_consolidate_extracts_entries(self):
        entries = analytics_memory._fallback_consolidate(
            [
                {"question": "整体情况", "intent": "OVERVIEW", "conclusion": "全站 3488 篇"},
                {"question": "", "intent": "OVERVIEW", "conclusion": "空问题忽略"},
            ]
        )
        self.assertTrue(entries)
        self.assertEqual("SESSION", entries[0]["scope"])
        self.assertGreaterEqual(entries[0]["importance"], 0.5)

    def test_dedupe_key_reuses_existing(self):
        with patch.object(analytics_memory.mysql, "query") as query:
            query.return_value = [
                {"memory_key": "existing.key", "content": "用户关注评论风险指标"}
            ]
            key = analytics_memory._dedupe_key("USER", 1, None, "proposed.key", "用户关注评论风险指标")
        self.assertEqual("existing.key", key)


class TemplateVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_verify = analytics_agent.settings.analytics_template_verify
        self._old_timeout = analytics_agent.settings.analytics_template_verify_timeout

    def tearDown(self) -> None:
        _set_setting("analytics_template_verify", self._old_verify)
        _set_setting("analytics_template_verify_timeout", self._old_timeout)

    def test_verifier_confirmed_keeps_template_path(self) -> None:
        _set_setting("analytics_template_verify", True)
        model = type("FakeModel", (), {"invoke": lambda self, messages: type("R", (), {"content": '{"confirmed": true, "intent": "HOT_ARTICLE"}'})()})()
        with (
            patch.object(type(analytics_agent.llm_client), "enabled", new_callable=PropertyMock, return_value=True),
            patch.object(analytics_agent, "llm_factory", return_value=model),
        ):
            payload = analytics_agent.detect_intent("按点赞数统计热门博客，返回前 10 篇")
        self.assertEqual("HOT_ARTICLE", payload["intent"])
        self.assertTrue(payload["llmSkipped"])
        self.assertTrue(payload["templateVerify"]["confirmed"])

    def test_verifier_rejected_downgrades_to_llm(self) -> None:
        _set_setting("analytics_template_verify", True)
        verifier_model = type(
            "FakeVerifierModel", (), {"invoke": lambda self, messages: type("R", (), {"content": '{"confirmed": false, "intent": "CUSTOM_SQL", "reason": "用户要求排除特定标签"}'})()}
        )()
        with (
            patch.object(type(analytics_agent.llm_client), "enabled", new_callable=PropertyMock, return_value=True),
            patch.object(analytics_agent, "llm_factory", return_value=verifier_model),
            patch.object(
                analytics_agent.llm_client,
                "complete_json",
                return_value={"intent": "CUSTOM_SQL", "confidence": 0.4},
            ),
        ):
            payload = analytics_agent.detect_intent("排除 Redis 标签的热门博客 TOP10")
        self.assertEqual("CUSTOM_SQL", payload["intent"])
        self.assertFalse(payload["llmSkipped"])
        self.assertFalse(payload["templateVerify"]["confirmed"])

    def test_verifier_unavailable_trusts_rules(self) -> None:
        _set_setting("analytics_template_verify", True)
        with patch.object(type(analytics_agent.llm_client), "enabled", new_callable=PropertyMock, return_value=False):
            payload = analytics_agent.detect_intent("按点赞数统计热门博客，返回前 10 篇")
        self.assertEqual("HOT_ARTICLE", payload["intent"])
        self.assertTrue(payload["llmSkipped"])
        self.assertEqual("verifier-unavailable-trust-rules", payload["templateVerify"]["reason"])

    def test_verifier_disabled_keeps_old_path(self) -> None:
        _set_setting("analytics_template_verify", False)
        with patch.object(type(analytics_agent.llm_client), "enabled", new_callable=PropertyMock, return_value=False):
            payload = analytics_agent.detect_intent("按点赞数统计热门博客，返回前 10 篇")
        self.assertEqual("HOT_ARTICLE", payload["intent"])
        self.assertTrue(payload["llmSkipped"])
        self.assertEqual("verifier-disabled", payload["templateVerify"]["reason"])


class SupervisorNodeTests(unittest.TestCase):
    def _state(self, **overrides) -> dict:
        state = {
            "question": "统计每个用户发布的文章数和总点赞数",
            "role": "ADMIN",
            "user_id": 1,
            "intent": "CUSTOM_SQL",
            "intent_confidence": 0.35,
            "analysis_spec": {"intent": "CUSTOM_SQL", "filters": {}, "limit": 10},
            "analysis_plan": {},
            "execution_plan": analytics_agent.new_execution_plan("test"),
            "memory": {"enabled": True, "long_term": [], "short_turns": [], "sessionMemory": []},
        }
        state.update(overrides)
        return state

    def test_template_route_skips_llm(self) -> None:
        state = self._state(intent="HOT_ARTICLE", intent_confidence=0.9, use_template_path=True)
        with patch.object(analytics_agent.llm_client, "complete_json") as complete:
            state = analytics_agent.supervisor_node(state)
        complete.assert_not_called()
        self.assertEqual("data_qa_template", state["supervisor"]["route"])
        self.assertEqual("deterministic", state["supervisor"]["mode"])

    def test_llm_route_generates_declaration(self) -> None:
        with patch.object(
            analytics_agent.llm_client,
            "complete_json",
            return_value={"declaration": "我将查询：每个用户的文章数与总点赞，按文章数排序", "taskSpec": {"goal": "x"}},
        ):
            state = analytics_agent.supervisor_node(self._state())
        self.assertEqual("data_qa_agent", state["supervisor"]["route"])
        self.assertEqual("llm", state["supervisor"]["mode"])
        self.assertIn("每个用户", state["supervisor"]["declaration"])

    def test_diagnostic_route_is_deterministic(self) -> None:
        state = self._state(diagnostic_keys=["engagement_rate"])
        with patch.object(analytics_agent.llm_client, "complete_json") as complete:
            state = analytics_agent.supervisor_node(state)
        complete.assert_not_called()
        self.assertEqual("anomaly_diagnosis", state["supervisor"]["route"])

    def test_supervisor_task_reaches_agent_loop_context(self) -> None:
        state = self._state()
        state["supervisor"] = {
            "declaration": "我将查询：每个用户的文章数",
            "route": "data_qa_agent",
            "taskSpec": {"goal": "按文章数排序的用户统计", "steps": ["统计文章数", "按文章数排序"]},
        }
        state = analytics_agent.agent_loop_init_node(state)
        user_content = state["messages"][1]["content"]
        self.assertIn("主管 Agent 下发的任务规格", user_content)
        self.assertIn("按文章数排序的用户统计", user_content)
        self.assertIn("统计文章数", user_content)


if __name__ == "__main__":
    unittest.main()
