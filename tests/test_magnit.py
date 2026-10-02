import unittest

from connectors.magnit import parse_magnit_search_page


class MagnitConnectorTests(unittest.TestCase):
    PAGE = """
    <article data-test-id="v-product-preview">
      <a title="Напиток Добрый Cola 1л"
         href="/product/100-dobryy?shopCode=42&amp;shopType=dostavka"
         data-test-id="v-app-link">
        <div class="unit-catalog-product-preview-prices__regular">
          <span>99.99&#8202;₽</span>
        </div>
        <span class="unit-catalog-product-preview-prices__sale">
          <span>129.99&#8202;₽</span>
        </span>
      </a>
    </article>
    <article data-test-id="v-product-preview">
      <a title="Напиток Добрый Cola без сахара 1л"
         href="/product/101-zero"
         data-test-id="v-app-link">
        <div class="unit-catalog-product-preview-prices__regular">
          <span>104,99&#8202;₽</span>
        </div>
      </a>
    </article>
    """

    def test_extracts_official_product_cards(self):
        offers = parse_magnit_search_page(self.PAGE)

        self.assertEqual(len(offers), 2)
        self.assertEqual(offers[0]["title"], "Напиток Добрый Кола 1л")
        self.assertEqual(offers[0]["price"], 99.99)
        self.assertEqual(offers[0]["old_price"], 129.99)
        self.assertEqual(offers[0]["store"], "🔴 Магнит")
        self.assertEqual(
            offers[0]["link"],
            "https://magnit.ru/product/100-dobryy?shopCode=42&shopType=dostavka",
        )

    def test_supports_comma_price_without_old_price(self):
        offers = parse_magnit_search_page(self.PAGE)

        self.assertEqual(offers[1]["price"], 104.99)
        self.assertIsNone(offers[1]["old_price"])


if __name__ == "__main__":
    unittest.main()
