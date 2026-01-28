import unittest
from unittest import mock

from HDRP.services.critic.nli_http_client import NLIHttpClient


class TestNLIHttpClient(unittest.TestCase):
    @mock.patch("HDRP.services.critic.nli_http_client.requests.post")
    def test_compute_relation_sends_variant_header(self, mock_post):
        mock_response = mock.Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "entailment": 0.9,
            "contradiction": 0.05,
            "neutral": 0.05,
        }
        mock_post.return_value = mock_response

        client = NLIHttpClient(base_url="http://nli.example")
        client.compute_relation("premise", "hypothesis", variant="exp")

        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["X-Model-Variant"], "exp")
        self.assertEqual(kwargs["json"]["premise"], "premise")
        self.assertEqual(kwargs["json"]["hypothesis"], "hypothesis")


if __name__ == "__main__":
    unittest.main()
