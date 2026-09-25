import unittest

from product_matching import is_relevant_result
from search_query import build_fallback_search_query


class GroceryMatchingTests(unittest.TestCase):
    def assert_matches(self, query: str, title: str) -> None:
        self.assertTrue(
            is_relevant_result(
                query,
                {"title": title},
            )
        )

    def assert_does_not_match(
        self,
        query: str,
        title: str,
    ) -> None:
        self.assertFalse(
            is_relevant_result(
                query,
                {"title": title},
            )
        )

    def test_beef_wording_variants_match(self):
        self.assert_matches(
            "фарш говяжий 500 г",
            "Фарш из говядины охлажденный 500 г",
        )

    def test_chicken_wording_variants_match(self):
        self.assert_matches(
            "фарш куриный 500 г",
            "Фарш из мяса цыплят охлажденный 500 г",
        )

    def test_wrong_weight_does_not_match(self):
        self.assert_does_not_match(
            "фарш говяжий 500 г",
            "Фарш из говядины охлажденный 400 г",
        )

    def test_exact_multipack_matches(self):
        self.assert_matches(
            "Corona Extra 0,33 л 6 бутылок",
            "Пиво Corona Extra 0.33 л, упаковка 6 бутылок",
        )

    def test_single_bottle_does_not_match_multipack(self):
        self.assert_does_not_match(
            "Corona Extra 0,33 л 6 бутылок",
            "Пиво Corona Extra 0.33 л, 1 бутылка",
        )

    def test_fallback_keeps_brand_and_volume(self):
        self.assertEqual(
            build_fallback_search_query(
                "Corona Extra 0,33 л 6 бутылок"
            ),
            "corona extra 0.33 l",
        )


if __name__ == "__main__":
    unittest.main()
