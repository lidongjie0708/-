import unittest

from app.ops_actions.service import ActionError, OperationActionPreviewService


class OperationActionPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = OperationActionPreviewService()

    def preview(self):
        return self.service.preview(
            actor_role="ADMIN", actor_id=1, action_type="TODO", target_type="BLOG", target_id="42",
            reason="Interaction rate declined", proposed_payload={"title": "Follow up"},
            idempotency_key="operation-action-test-key", evidence=[]
        )

    def test_non_admin_cannot_preview(self) -> None:
        with self.assertRaises(PermissionError):
            self.service.preview(
                actor_role="USER", actor_id=2, action_type="TODO", target_type="BLOG", target_id="42",
                reason="x", proposed_payload={}, idempotency_key="operation-action-user-key"
            )

    def test_only_safe_action_types_are_accepted(self) -> None:
        with self.assertRaises(ActionError):
            self.service.preview(
                actor_role="ADMIN", actor_id=1, action_type="UNPUBLISH", target_type="BLOG", target_id="42",
                reason="x", proposed_payload={}, idempotency_key="operation-action-unsafe-key"
            )

    def test_preview_is_not_actionable_or_persisted(self) -> None:
        preview = self.preview()
        self.assertFalse(preview["actionable"])
        self.assertEqual("none", preview["persistence"])
        self.assertEqual("JAVA_COMMAND_OUTBOX", preview["nextIntegrationPoint"])
        self.assertNotIn("status", preview)

    def test_seo_draft_requires_payload(self) -> None:
        with self.assertRaisesRegex(ActionError, "requires a proposedPayload"):
            self.service.preview(
                actor_role="ADMIN", actor_id=1, action_type="SEO_DRAFT", target_type="BLOG", target_id="42",
                reason="x", proposed_payload={}, idempotency_key="operation-action-seo-key"
            )


if __name__ == "__main__":
    unittest.main()
