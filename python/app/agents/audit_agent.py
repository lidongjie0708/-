from __future__ import annotations

from app.infra.llm import llm_client


HIGH_RISK_WORDS = ["赌博", "诈骗", "病毒", "木马", "暴力威胁"]
MEDIUM_RISK_WORDS = ["广告", "加微信", "返利", "兼职", "引流"]


def audit_content(content_type: str, content: str, user_id: int | None = None) -> dict:
    lowered = content.lower()
    if any(word in lowered for word in HIGH_RISK_WORDS):
        fallback = {
            "riskLevel": "HIGH",
            "passed": False,
            "reason": "命中高风险词，建议自动拦截。",
            "suggestion": "自动拦截并记录审核日志。",
        }
    elif any(word in lowered for word in MEDIUM_RISK_WORDS):
        fallback = {
            "riskLevel": "MEDIUM",
            "passed": False,
            "reason": "存在疑似广告或引流内容。",
            "suggestion": "进入人工审核队列。",
        }
    else:
        fallback = {
            "riskLevel": "LOW",
            "passed": True,
            "reason": "未发现明显风险。",
            "suggestion": "允许通过。",
        }
    return llm_client.complete_json(
        "你是内容审核 Agent。输出 JSON：riskLevel(LOW/MEDIUM/HIGH), passed, reason, suggestion。",
        f"类型：{content_type}\n用户：{user_id}\n内容：{content[:4000]}",
        fallback,
    )


def audit_comment(content: str, user_id: int | None = None) -> dict:
    audit = audit_content("comment", content, user_id)
    sentiment = -0.6 if audit["riskLevel"] in {"MEDIUM", "HIGH"} else 0.6
    return {
        "is_approved": audit["riskLevel"] == "LOW",
        "sentiment_score": sentiment,
        "risk_level": audit["riskLevel"],
        "reason": audit["reason"],
        "suggestion": audit["suggestion"],
    }
