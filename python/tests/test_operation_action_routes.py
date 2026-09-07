import unittest

from fastapi.testclient import TestClient

from app.api.routes import verify_agent_token
from app.infra.auth import AgentPrincipal
from app.main import app


PREVIEW_URL = "/api/agent/operations/actions/preview"
PREVIEW_PAYLOAD = {
    "type": "TODO",
    "targetType": "BLOG",
    "targetId": "42",
    "reason": "Engagement is below its historical baseline",
    "proposedPayload": {"title": "Review content performance"},
    "evidence": [],
    "idempotencyKey": "route-preview-test-key",
}


class OperationActionRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        app.dependency_overrides.clear()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @staticmethod
    def _principal(role: str) -> AgentPrincipal:
        return AgentPrincipal(username=role.lower(), user_id=7, role=role, scope="agent:stream")

    def test_non_admin_preview_returns_forbidden_application_code(self) -> None:
        app.dependency_overrides[verify_agent_token] = lambda: self._principal("USER")

        response = self.client.post(PREVIEW_URL, json=PREVIEW_PAYLOAD)

        # The established ApiResponse contract represents authorization failures
        # in its `code` field while retaining a valid response envelope.
        self.assertEqual(200, response.status_code)
        self.assertEqual(403, response.json()["code"])
        self.assertEqual("forbidden", response.json()["message"])

    def test_admin_preview_is_explicitly_non_actionable(self) -> None:
        app.dependency_overrides[verify_agent_token] = lambda: self._principal("ADMIN")

        response = self.client.post(PREVIEW_URL, json=PREVIEW_PAYLOAD)

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(0, body["code"])
        proposal = body["data"]["proposal"]
        self.assertFalse(proposal["actionable"])
        self.assertEqual("none", proposal["persistence"])
        self.assertEqual("JAVA_COMMAND_OUTBOX", proposal["nextIntegrationPoint"])

    def test_python_api_does_not_expose_action_lifecycle_routes(self) -> None:
        paths = {route.path for route in app.routes}

        self.assertNotIn("/api/agent/operations/actions/create", paths)
        self.assertNotIn("/api/agent/operations/actions/approve", paths)
        self.assertNotIn("/api/agent/operations/actions/execute", paths)


if __name__ == "__main__":
    unittest.main()
