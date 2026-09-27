#!/usr/bin/env python3
"""Steam Community Market price checker for CS2 items."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


API_URL = "https://steamcommunity.com/market/priceoverview/"


@dataclass
class PriceResult:
    item: str
    success: bool
    lowest_price: str | None = None
    median_price: str | None = None
    volume: str | None = None
    error: str | None = None


def fetch_price(item_name: str, appid: int = 730, currency: int = 1, country: str = "US") -> PriceResult:
    query = urlencode(
        {
            "appid": appid,
            "currency": currency,
            "country": country,
            "market_hash_name": item_name,
        }
    )
    request_url = f"{API_URL}?{query}"

    try:
        with urlopen(request_url, timeout=15) as response:  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        return PriceResult(item=item_name, success=False, error=str(exc))
    except json.JSONDecodeError as exc:
        return PriceResult(item=item_name, success=False, error=f"Invalid JSON response: {exc}")

    if not payload.get("success"):
        return PriceResult(item=item_name, success=False, error="Steam returned success=false")

    return PriceResult(
        item=item_name,
        success=True,
        lowest_price=payload.get("lowest_price"),
        median_price=payload.get("median_price"),
        volume=payload.get("volume"),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Steam market prices for CS2 items.")
    parser.add_argument("items", nargs="*", help="CS2 market item names (market_hash_name values).")
    parser.add_argument("-f", "--file", help="Path to a file containing one item name per line.")
    parser.add_argument("--currency", type=int, default=1, help="Steam currency code (default: 1=USD).")
    parser.add_argument("--country", default="US", help="Country code used by Steam market request (default: US).")
    return parser.parse_args()


def read_items(args: argparse.Namespace) -> list[str]:
    items: list[str] = list(args.items)

    if args.file:
        try:
            with open(args.file, encoding="utf-8") as file:
                items.extend(line.strip() for line in file if line.strip())
        except OSError as exc:
            print(f"Item file could not be read: {exc}", file=sys.stderr)
            return []

    return list(dict.fromkeys(items))


def print_results(results: Iterable[PriceResult]) -> None:
    for result in results:
        if result.success:
            print(
                f"{result.item}\n"
                f"  Lowest: {result.lowest_price or '-'}\n"
                f"  Median: {result.median_price or '-'}\n"
                f"  Volume: {result.volume or '-'}"
            )
        else:
            print(f"{result.item}\n  Error: {result.error or 'Unknown error'}")


def main() -> int:
    args = parse_args()
    items = read_items(args)

    if not items:
        print("No item provided. Use arguments and/or --file to define item names.", file=sys.stderr)
        return 1

    results = [fetch_price(item, currency=args.currency, country=args.country) for item in items]
    print_results(results)

    return 0 if all(result.success for result in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
