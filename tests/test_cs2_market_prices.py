import tempfile
import unittest
from argparse import Namespace
from unittest.mock import patch

import cs2_market_prices


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class TestCS2MarketPrices(unittest.TestCase):
    def test_read_items_from_args_and_file_deduplicates(self):
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as file:
            file.write("AWP | Asiimov (Battle-Scarred)\nAK-47 | Redline (Field-Tested)\n")
            file.flush()
            args = Namespace(
                items=["AK-47 | Redline (Field-Tested)"],
                file=file.name,
                currency=1,
                country="US",
            )
            items = cs2_market_prices.read_items(args)

        self.assertEqual(
            items,
            ["AK-47 | Redline (Field-Tested)", "AWP | Asiimov (Battle-Scarred)"],
        )

    @patch("cs2_market_prices.urlopen")
    def test_fetch_price_parses_success_response(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(
            b'{"success": true, "lowest_price": "$5.00", "median_price": "$5.10", "volume": "123"}'
        )

        result = cs2_market_prices.fetch_price("AK-47 | Redline (Field-Tested)")

        self.assertTrue(result.success)
        self.assertEqual(result.lowest_price, "$5.00")
        self.assertEqual(result.median_price, "$5.10")
        self.assertEqual(result.volume, "123")

    def test_main_returns_1_when_no_items(self):
        with patch("cs2_market_prices.parse_args", return_value=Namespace(items=[], file=None, currency=1, country="US")):
            exit_code = cs2_market_prices.main()

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
