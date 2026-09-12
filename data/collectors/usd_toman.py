import os
import requests
from datetime import datetime, timezone


NETARZ_URL = "https://netarz.ir/api/fx/v1/rates/USD"


def get_usd_toman():
    """
    دریافت نرخ دلار آمریکا به تومان از NetArz.

    خروجی:
    - buy
    - sell
    - mid
    - change_24h_percent
    """

    api_key = os.getenv("NETARZ_FX_KEY")

    if not api_key:
        raise RuntimeError(
            "NETARZ_FX_KEY environment variable is not set"
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    requested_at = datetime.now(timezone.utc)

    try:

        response = requests.get(
            NETARZ_URL,
            headers=headers,
            timeout=10,
        )

    except requests.Timeout as exc:

        raise RuntimeError(
            "NetArz request timed out"
        ) from exc

    except requests.RequestException as exc:

        raise RuntimeError(
            f"NetArz request failed: {exc}"
        ) from exc

    # --------------------------------------------------------
    # HTTP ERRORS
    # --------------------------------------------------------

    if response.status_code == 401:
        raise RuntimeError(
            "NetArz authentication failed. "
            "Check NETARZ_FX_KEY."
        )

    if response.status_code == 403:
        raise RuntimeError(
            "NetArz access denied. "
            "The app/domain/IP may not be authorized."
        )

    if response.status_code == 429:
        raise RuntimeError(
            "NetArz rate limit or daily quota reached."
        )

    try:

        response.raise_for_status()

    except requests.HTTPError as exc:

        raise RuntimeError(
            f"NetArz HTTP error: "
            f"{response.status_code}"
        ) from exc

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    try:

        result = response.json()

    except ValueError as exc:

        raise RuntimeError(
            "NetArz returned invalid JSON"
        ) from exc

    if not isinstance(result, dict):

        raise RuntimeError(
            "Unexpected NetArz response type"
        )

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    data = result.get("data")

    meta = result.get("meta", {})

    if not isinstance(data, dict):

        raise RuntimeError(
            f"NetArz response does not contain valid data: "
            f"{result}"
        )

    buy = data.get("buy")
    sell = data.get("sell")
    mid = data.get("mid")

    if buy is None:
        raise RuntimeError(
            "NetArz response does not contain 'buy'"
        )

    if sell is None:
        raise RuntimeError(
            "NetArz response does not contain 'sell'"
        )

    if mid is None:
        raise RuntimeError(
            "NetArz response does not contain 'mid'"
        )

    try:

        buy_toman = float(buy)
        sell_toman = float(sell)
        mid_toman = float(mid)

    except (TypeError, ValueError) as exc:

        raise RuntimeError(
            "Invalid USD prices returned by NetArz"
        ) from exc

    if buy_toman <= 0:
        raise RuntimeError(
            f"Invalid USD buy price: {buy_toman}"
        )

    if sell_toman <= 0:
        raise RuntimeError(
            f"Invalid USD sell price: {sell_toman}"
        )

    if mid_toman <= 0:
        raise RuntimeError(
            f"Invalid USD mid price: {mid_toman}"
        )

    return {
        "source": "netarz",
        "symbol": "USD_TOMAN",

        "buy": buy_toman,
        "sell": sell_toman,
        "mid": mid_toman,

        "price": mid_toman,
        "price_toman": mid_toman,

        "currency": "TOMAN",

        "change_24h_percent": data.get(
            "change_24h_percent"
        ),

        "as_of": meta.get("as_of"),

        "delayed_minutes": meta.get(
            "delayed_minutes"
        ),

        "is_delayed": meta.get(
            "is_delayed"
        ),

        "requested_at": requested_at.isoformat(),

        "raw": result,
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 50)
    print("💵 USD / TOMAN TEST")
    print("=" * 50)

    try:

        result = get_usd_toman()

        print(
            f"Source:       {result['source']}"
        )

        print(
            f"Symbol:       {result['symbol']}"
        )

        print(
            f"Buy:          "
            f"{result['buy']:,.0f} تومان"
        )

        print(
            f"Sell:         "
            f"{result['sell']:,.0f} تومان"
        )

        print(
            f"Mid:          "
            f"{result['mid']:,.0f} تومان"
        )

        print(
            f"24h Change:   "
            f"{result['change_24h_percent']}%"
        )

        print(
            f"As Of:        "
            f"{result['as_of']}"
        )

        print(
            f"Delayed:      "
            f"{result['delayed_minutes']} min"
        )

        print(
            f"Requested:    "
            f"{result['requested_at']}"
        )

    except Exception as error:

        print("❌ USD/TOMAN ERROR:")
        print(
            f"Type: {type(error).__name__}"
        )
        print(
            f"Message: {error}"
        )
