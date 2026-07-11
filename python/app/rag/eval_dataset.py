from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RagEvalCaseItem:
    question: str
    ground_truth: str | None = None
    reference: str | None = None
    contexts: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)


DEFAULT_RAG_EVAL_SET = [
    RagEvalCaseItem(
        question="最近高互动文章有哪些共同主题？",
        ground_truth="应根据博客知识库中召回的文章主题、标签和互动数据回答，并引用来源。",
        expected_keywords=["主题", "标签", "互动"],
    ),
    RagEvalCaseItem(
        question="哪些文章适合补充内部链接？",
        ground_truth="应识别相关主题文章并给出可互链的理由，回答需要带引用。",
        expected_keywords=["内部链接", "相关", "引用"],
    ),
    RagEvalCaseItem(
        question="近期评论反馈暴露了哪些内容优化机会？",
        ground_truth="应结合评论或文章上下文总结优化机会，并避免无来源推断。",
        expected_keywords=["评论", "优化", "反馈"],
    ),
]


def normalize_eval_cases(cases: list[dict] | None) -> list[RagEvalCaseItem]:
    if not cases:
        return DEFAULT_RAG_EVAL_SET
    return [
        RagEvalCaseItem(
            question=item["question"],
            ground_truth=item.get("groundTruth") or item.get("ground_truth"),
            reference=item.get("reference"),
            contexts=item.get("contexts") or [],
            expected_keywords=item.get("expectedKeywords") or item.get("expected_keywords") or [],
        )
        for item in cases
    ]
