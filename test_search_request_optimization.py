import unittest
from retailer_links import (
    is_likely_grocery_query,
    large_retailers_for_query,
    retailer_url_for_query,
)


class SearchRequestOptimizationTests(unittest.TestCase):
    def test_detects_grocery_query_without_external_request(self):
        self.assertTrue(is_likely_grocery_query("Добрый кола 1 л"))
        self.assertTrue(
            is_likely_grocery_query(
                "пиво Балтика 7",
                age_restricted=True,
            )
        )
        self.assertFalse(is_likely_grocery_query("iPhone 17 Pro 256 GB"))

    def test_grocery_links_include_all_requested_major_chains(self):
        retailers = dict(large_retailers_for_query())

        for retailer in (
            "🟢 Пятёрочка",
            "🟢 Перекрёсток",
            "🔴 Магнит",
            "🟠 Дикси",
            "🟢 ВкусВилл",
            "🟣 Азбука Вкуса",
            "🟡 Чижик",
            "🔴 Светофор",
        ):
            self.assertIn(retailer, retailers)

        self.assertNotIn("🔞 ВинЛаб", retailers)
        self.assertNotIn("🔞 Красное & Белое", retailers)

    def test_alcohol_links_add_adult_retailers(self):
        retailers = dict(
            large_retailers_for_query(age_restricted=True)
        )

        self.assertIn("🔞 ВинЛаб", retailers)
        self.assertIn("🔞 Красное & Белое", retailers)

    def test_verified_retailer_search_links_include_product_query(self):
        retailers = dict(
            large_retailers_for_query("Добрый кола 1 л")
        )

        self.assertEqual(
            retailers["🟢 Перекрёсток"],
            "https://www.perekrestok.ru/cat/search?"
            "search=%D0%94%D0%BE%D0%B1%D1%80%D1%8B%D0%B9+"
            "%D0%BA%D0%BE%D0%BB%D0%B0+1+%D0%BB",
        )
        self.assertEqual(
            retailers["🟢 ВкусВилл"],
            "https://vkusvill.ru/search/?q="
            "%D0%94%D0%BE%D0%B1%D1%80%D1%8B%D0%B9+"
            "%D0%BA%D0%BE%D0%BB%D0%B0+1+%D0%BB",
        )

    def test_unverified_retailer_keeps_official_homepage(self):
        self.assertEqual(
            retailer_url_for_query(
                "🟢 Пятёрочка",
                "https://5ka.ru/",
                "Добрый кола 1 л",
            ),
            "https://5ka.ru/",
        )

if __name__ == "__main__":
    unittest.main()
