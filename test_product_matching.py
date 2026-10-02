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

    def test_different_cola_brand_does_not_match(self):
        self.assert_does_not_match(
            "Добрый кола 1 л",
            "Отзывы: Напиток газированный Evervess Кола, 1 л",
        )

    def test_plain_cola_rejects_zero_sugar_variant(self):
        self.assert_does_not_match(
            "Добрый кола 1 л",
            "Напиток газированный Добрый Кола без сахара 1 л",
        )

    def test_zero_sugar_query_matches_zero_sugar_variant(self):
        self.assert_matches(
            "Добрый кола без сахара 1 л",
            "Напиток газированный Добрый Кола без сахара 1 л",
        )

    def test_zero_sugar_query_rejects_regular_variant(self):
        self.assert_does_not_match(
            "Добрый кола без сахара 1 л",
            "Напиток газированный Добрый Кола 1 л",
        )

    def test_zero_aliases_are_recognized(self):
        self.assert_matches(
            "Добрый кола зеро 1 л",
            "Напиток газированный Добрый Кола Зеро 1 л",
        )

    def test_single_bottle_rejects_numeric_multipack(self):
        self.assert_does_not_match(
            "Добрый кола 1 л",
            "ДОБРЫЙ Кола напиток газ 12*1л ПЭТ",
        )

    def test_single_bottle_rejects_parenthesized_case_count(self):
        self.assert_does_not_match(
            "Добрый кола 1 л",
            "Добрый 1л. ПЭТ. (12) Кола (бывший Кока-Кола)",
        )

    def test_single_bottle_rejects_piece_count_multipack(self):
        self.assert_does_not_match(
            "Добрый кола 1 л",
            "Добрый Кола 1 л, упаковка 12 шт",
        )

    def test_explicit_piece_count_matches(self):
        self.assert_matches(
            "Добрый кола 1 л 12 шт",
            "Добрый Кола 1 л, упаковка 12 шт",
        )

    def test_unspecified_diaper_count_remains_allowed(self):
        self.assert_matches(
            "Pampers Premium Care размер 4",
            "Подгузники Pampers Premium Care размер 4, 52 шт",
        )

    def test_plain_cola_rejects_flavoured_variant(self):
        self.assert_does_not_match(
            "Добрый кола 1 л",
            "Напиток Добрый Кола Дыня 1 л",
        )

    def test_requested_flavour_matches(self):
        self.assert_matches(
            "Добрый кола ваниль 1 л",
            "Напиток Добрый Кола со вкусом ванили 1 л",
        )


if __name__ == "__main__":
    unittest.main()
