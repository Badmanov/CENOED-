import unittest
import sys
from unittest.mock import Mock, patch

sys.modules.setdefault("requests", Mock())

from connectors import google_shopping


class SearchProviderFallbackTests(unittest.TestCase):
    @patch("connectors.google_shopping.requests.get")
    def test_uses_serpapi_when_scrapedo_fails(self, request_get):
        failed = Mock()
        failed.raise_for_status.side_effect = RuntimeError("quota")

        fallback = Mock()
        fallback.raise_for_status.return_value = None
        fallback.json.return_value = {"shopping_results": []}
        request_get.side_effect = [failed, fallback]

        with patch.object(google_shopping, "SCRAPEDO_TOKEN", "primary"), patch.object(
            google_shopping,
            "SERPAPI_KEY",
            "reserve",
        ):
            data = google_shopping._fetch_shopping_data(
                "iPhone",
                "Москва, Россия",
            )

        self.assertEqual(data, {"shopping_results": []})
        self.assertEqual(request_get.call_count, 2)
        reserve_params = request_get.call_args_list[1].kwargs["params"]
        self.assertEqual(reserve_params["engine"], "google_shopping")
        self.assertEqual(reserve_params["api_key"], "reserve")


if __name__ == "__main__":
    unittest.main()
