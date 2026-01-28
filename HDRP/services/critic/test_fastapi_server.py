import importlib
import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient


def _load_server_module() -> object:
    import HDRP.services.critic.fastapi_server as fastapi_server

    return importlib.reload(fastapi_server)


class FakeVerifier:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def _ensure_model_loaded(self) -> None:
        return None

    def compute_relation(self, premise: str, hypothesis: str):
        return {"entailment": 0.9, "contradiction": 0.1, "neutral": 0.0}


class TestFastAPIServer(unittest.TestCase):
    def setUp(self):
        self.env_patch = mock.patch.dict(
            os.environ,
            {
                "HDRP_NLI_VARIANTS": "control=model-a,exp=model-b",
                "HDRP_NLI_VARIANT_DEFAULT": "control",
                "HDRP_NLI_HTTP_PORT": "8001",
            },
        )
        self.env_patch.start()

        self.server = _load_server_module()
        self.verifier_patch = mock.patch.object(self.server, "NLIVerifier", FakeVerifier)
        self.verifier_patch.start()

    def tearDown(self):
        self.verifier_patch.stop()
        self.env_patch.stop()

    def test_health_lists_variants(self):
        with TestClient(self.server.app) as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("control", payload["variants"])
        self.assertIn("exp", payload["variants"])

    def test_relation_uses_header_variant(self):
        with TestClient(self.server.app) as client:
            response = client.post(
                "/relation",
                json={"premise": "a", "hypothesis": "b"},
                headers={"X-Model-Variant": "exp"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["variant"], "exp")

    def test_relation_rejects_unknown_variant(self):
        with TestClient(self.server.app) as client:
            response = client.post(
                "/relation",
                json={"premise": "a", "hypothesis": "b"},
                headers={"X-Model-Variant": "unknown"},
            )
        self.assertEqual(response.status_code, 400)

    def test_metrics_endpoint(self):
        with TestClient(self.server.app) as client:
            response = client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
