import unittest

from connectors.google_search import (
    _extract_price,
    _retailer_name,
)


class GoogleSearchConnectorTests(unittest.TestCase):
    def test_extracts_ruble_price(self):
        self.assertEqual(
            _extract_price(
                {
                    "title": "Corona Extra",
                    "snippet": "119 ₽ вместо 166 ₽",
                }
            ),
            119.0,
        )

    def test_ignores_result_without_price(self):
        self.assertIsNone(
            _extract_price(
                {
                    "title": "Corona Extra",
                    "snippet": "Цена уточняется",
                }
            )
        )

    def test_marks_yandex_market(self):
        self.assertEqual(
            _retailer_name(
                "https://m.integration.vs.market.yandex.net/card/123"
            ),
            "🟨 Яндекс Маркет",
        )

    def test_rejects_unknown_domain(self):
        self.assertIsNone(
            _retailer_name(
                "https://example.com/product"
            )
        )


if __name__ == "__main__":
    unittest.main()
