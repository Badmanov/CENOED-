import unittest

from connectors.google_search import (
    _extract_price,
    _is_product_link,
    _retailer_search_hint,
    _retailer_name,
    STORE_SELECTION_RETAILERS,
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

    def test_accepts_yandex_product_card(self):
        self.assertTrue(
            _is_product_link(
                "https://market.yandex.ru/card/corona-extra/123"
            )
        )

    def test_rejects_yandex_search_page(self):
        self.assertFalse(
            _is_product_link(
                "https://market.yandex.ru/search?text=nolinskie"
            )
        )

    def test_accepts_direct_marketplace_cards(self):
        self.assertTrue(
            _is_product_link(
                "https://www.ozon.ru/product/iphone-17-pro-123456/"
            )
        )
        self.assertTrue(
            _is_product_link(
                "https://www.wildberries.ru/catalog/123456/detail.aspx"
            )
        )

    def test_rejects_marketplace_search_pages(self):
        self.assertFalse(
            _is_product_link(
                "https://www.ozon.ru/search/?text=iphone"
            )
        )
        self.assertFalse(
            _is_product_link(
                "https://www.wildberries.ru/catalog/0/search.aspx"
            )
        )

    def test_accepts_kb_product_and_rejects_category(self):
        self.assertTrue(
            _is_product_link(
                "https://krasnoeibeloe.ru/catalog/importnoe_pivo/napitok_pivnoy_korona_ekstra/"
            )
        )
        self.assertFalse(
            _is_product_link(
                "https://krasnoeibeloe.ru/catalog/importnoe_pivo/"
            )
        )

    def test_search_hint_covers_every_supported_retailer(self):
        hint = _retailer_search_hint()
        for domain in (
            "market.yandex.ru",
            "ozon.ru",
            "wildberries.ru",
            "perekrestok.ru",
            "5ka.ru",
            "dixy.ru",
            "magnit.ru",
            "vkusvill.ru",
            "av.ru",
            "winelab.ru",
            "krasnoeibeloe.ru",
        ):
            self.assertIn(f"site:{domain}", hint)

    def test_store_selection_retailers_are_explicit(self):
        self.assertIn(
            "🔞 Красное & Белое",
            STORE_SELECTION_RETAILERS,
        )
        self.assertIn(
            "🟢 Пятёрочка",
            STORE_SELECTION_RETAILERS,
        )
        self.assertNotIn(
            "🟦 Ozon",
            STORE_SELECTION_RETAILERS,
        )


if __name__ == "__main__":
    unittest.main()
