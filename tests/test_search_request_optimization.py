import unittest
from retailer_links import (
    is_likely_grocery_query,
    large_retailers_for_query,
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

if __name__ == "__main__":
    unittest.main()
