from __future__ import annotations

from typing import Any


def build_publish_result(audit: dict[str, Any], auto_publish: bool) -> dict[str, Any]:
    risk = audit.get("riskLevel", "MEDIUM")
    if risk == "LOW" and auto_publish:
        return {"decision": "ALLOW_PUBLISH", "message": "Content passed audit and can be published."}
    if risk == "LOW":
        return {"decision": "SAVE_DRAFT", "message": "Content passed audit and was saved as draft."}
    if risk == "MEDIUM":
        return {"decision": "HUMAN_REVIEW", "message": "Content needs manual review."}
    return {"decision": "REJECT", "message": "Content was blocked by audit."}
