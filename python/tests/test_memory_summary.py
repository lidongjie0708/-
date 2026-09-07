import unittest

from app.rag.memory_summary import normalize_summary, render_summary


class MemorySummaryTests(unittest.TestCase):
    def test_normalize_summary_limits_and_keeps_schema(self) -> None:
        value = normalize_summary({"conversationGoal": "g" * 200, "confirmedFacts": ["fact"] * 20, "summary": "ok"})
        self.assertEqual(160, len(value["conversationGoal"]))
        self.assertEqual(8, len(value["confirmedFacts"]))
        self.assertEqual("ok", value["summary"])
        self.assertIn("openQuestions", value)

    def test_render_summary_respects_prompt_budget(self) -> None:
        text = render_summary({"conversationGoal": "设计记忆", "confirmedFacts": ["使用 MySQL"], "preferences": [], "openQuestions": [], "importantEntities": [], "summary": "x" * 100}, 60)
        self.assertLessEqual(len(text), 60)
        self.assertIn("会话目标", text)


if __name__ == "__main__":
    unittest.main()
