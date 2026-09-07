from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ActionType(StrEnum):
    TODO = "TODO"
    SEO_DRAFT = "SEO_DRAFT"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ActionError(ValueError):
    """A safe domain failure which callers can expose as a 4xx response."""


class OperationActionPreviewService:
    """Validate and render operation proposals without creating a command.

    Python intentionally does not persist, approve, enqueue, or execute operation
    actions. A future Java Command API is the only permitted integration point for
    approval, Outbox publication, idempotency persistence, and business writes.
    """

    @staticmethod
    def _require_admin(role: str) -> None:
        if role.upper() != "ADMIN":
            raise PermissionError("Only administrators can preview operation actions")

    @staticmethod
    def _validate_type(action_type: str) -> ActionType:
        try:
            return ActionType(action_type)
        except ValueError as exc:
            raise ActionError("Only TODO and SEO_DRAFT proposals are enabled in this release") from exc

    def preview(
        self,
        *,
        actor_role: str,
        actor_id: int | None,
        action_type: str,
        target_type: str,
        target_id: str,
        reason: str,
        proposed_payload: dict[str, Any],
        idempotency_key: str,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self._require_admin(actor_role)
        validated_type = self._validate_type(action_type)
        if not idempotency_key.strip():
            raise ActionError("idempotencyKey is required")
        if not target_type.strip() or not target_id.strip() or not reason.strip():
            raise ActionError("targetType, targetId and reason are required")
        if validated_type is ActionType.SEO_DRAFT and not proposed_payload:
            raise ActionError("SEO_DRAFT requires a proposedPayload")

        return {
            "previewId": str(uuid4()),
            "type": validated_type.value,
            "targetType": target_type,
            "targetId": target_id,
            "reason": reason,
            "proposedPayload": proposed_payload,
            "evidence": evidence or [],
            "riskLevel": RiskLevel.LOW.value,
            "idempotencyKey": idempotency_key,
            "requestedBy": actor_id,
            "generatedAt": datetime.now(UTC).isoformat(),
            "actionable": False,
            "persistence": "none",
            "nextIntegrationPoint": "JAVA_COMMAND_OUTBOX",
            "message": "Preview only. Python did not create, approve, enqueue, or execute an operation action.",
        }


action_preview_service = OperationActionPreviewService()
