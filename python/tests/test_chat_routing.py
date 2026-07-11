import unittest

from app.agents.chat_orchestrator import route_chat


class Principal:
    def __init__(self, role: str) -> None:
        self.role = role


class ChatRoutingTests(unittest.TestCase):
    def assert_mode(self, text: str, role: str, expected: str) -> None:
        decision = route_chat(text, "auto", Principal(role))
        self.assertEqual(expected, decision["mode"], decision)

    def test_concept_explanation_stays_in_chat(self) -> None:
        self.assert_mode("解释一下 RAG 是什么", "USER", "chat")
        self.assert_mode("介绍一下运营 Agent 是什么", "ADMIN", "chat")

    def test_blog_retrieval_routes_to_rag(self) -> None:
        self.assert_mode("博客中有哪些关于 Redis 的文章", "USER", "rag")
        self.assert_mode("根据知识库总结点赞系统的设计", "USER", "rag")

    def test_metrics_route_to_analytics_for_admin(self) -> None:
        self.assert_mode("最近点赞最多的十篇文章", "ADMIN", "analytics")
        self.assert_mode("本月新增用户趋势怎么样", "ADMIN", "analytics")

    def test_analytics_is_not_available_to_regular_user(self) -> None:
        self.assert_mode("最近点赞最多的文章", "USER", "chat")

    def test_explicit_mode_has_priority(self) -> None:
        decision = route_chat("最近点赞最多的文章", "rag", Principal("ADMIN"))
        self.assertEqual("rag", decision["mode"])
        self.assertEqual(1.0, decision["confidence"])
        self.assertEqual("explicit", decision["policy"])

    def test_mixed_retrieval_and_metrics_abstains(self) -> None:
        decision = route_chat("根据博客内容分析点赞趋势", "auto", Principal("ADMIN"))
        self.assertEqual("chat", decision["mode"], decision)
        self.assertTrue(decision["needsClarification"], decision)
        self.assertEqual({"rag", "analytics"}, set(decision["suggestedModes"]))

    def test_route_decision_is_observable(self) -> None:
        decision = route_chat("博客中有哪些 Redis 文章", "auto", Principal("USER"))
        self.assertEqual("hybrid-v2", decision["routerVersion"])
        self.assertIn("policy", decision)
        self.assertIn("candidates", decision)


if __name__ == "__main__":
    unittest.main()
