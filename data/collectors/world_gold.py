import requests
from datetime import datetime, timezone


WORLD_GOLD_URL = "https://api.gold-api.com/price/XAU"


def get_world_gold():
    """
    دریافت قیمت جهانی طلا (XAU/USD).

    قیمت بر حسب دلار آمریکا برای هر اونس تروا است.
    """

    requested_at = datetime.now(timezone.utc)

    try:
        response = requests.get(
            WORLD_GOLD_URL,
            timeout=10,
        )

        response.raise_for_status()

    except requests.Timeout as exc:
        raise RuntimeError(
            "World Gold API request timed out"
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            f"World Gold API request failed: {exc}"
        ) from exc

    try:
        data = response.json()

    except ValueError as exc:
        raise RuntimeError(
            "World Gold API returned invalid JSON"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Unexpected World Gold response type: "
            f"{type(data).__name__}"
        )

    # Gold API returns the XAU price in USD/oz.
    price = data.get("price")

    if price is None:
        raise RuntimeError(
            f"World Gold response does not contain 'price': {data}"
        )

    try:
        price_usd = float(price)

    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid World Gold price: {price}"
        ) from exc

    if price_usd <= 0:
        raise RuntimeError(
            f"Invalid World Gold price: {price_usd}"
        )

    return {
        "source": "gold_api",
        "symbol": "XAU_USD",
        "price_usd": price_usd,
        "currency": "USD",
        "unit": "troy_ounce",
        "timestamp": requested_at.isoformat(),
        "raw": data,
    }


if __name__ == "__main__":
    print("=" * 50)
    print("🌎 WORLD GOLD TEST")
    print("=" * 50)

    try:
        result = get_world_gold()

        print(f"Source:       {result['source']}")
        print(f"Symbol:       {result['symbol']}")
        print(f"Price:        ${result['price_usd']:,.2f}")
        print(f"Unit:         {result['unit']}")
        print(f"Timestamp:    {result['timestamp']}")
        print(f"Raw response: {result['raw']}")

    except Exception as exc:
        print("❌ WORLD GOLD ERROR:")
        print(type(exc).__name__)
        print(exc)
