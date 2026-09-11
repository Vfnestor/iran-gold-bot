import os
import requests
from datetime import datetime, timezone


SERVIX_URL = "https://servix.cc/api/v1/assets/GOLD_18_RLS"
SERVIX_API_KEY = os.getenv("SERVIX_API_KEY")


def get_servix_gold():
    """
    دریافت آخرین قیمت طلای 18 عیار از Servix.

    قیمت API بر حسب ریال است.
    """

    if not SERVIX_API_KEY:
        raise RuntimeError(
            "SERVIX_API_KEY environment variable is not set"
        )

    headers = {
        "X-API-Key": SERVIX_API_KEY,
        "Accept": "application/json",
    }

    requested_at = datetime.now(timezone.utc)

    try:
        response = requests.get(
            SERVIX_URL,
            headers=headers,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Servix request failed: {exc}"
        ) from exc

    except ValueError as exc:
        raise RuntimeError(
            "Servix returned invalid JSON"
        ) from exc

    # بررسی ساختار پاسخ
    if not isinstance(data, dict):
        raise RuntimeError(
            f"Unexpected Servix response type: {type(data).__name__}"
        )

    if data.get("code") != "GOLD_18_RLS":
        raise RuntimeError(
            f"Unexpected Servix asset code: {data.get('code')}"
        )

    value = data.get("value")

    if value is None:
        raise RuntimeError(
            "Servix response does not contain 'value'"
        )

    try:
        price_riel = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid Servix price value: {value}"
        ) from exc

    if price_riel <= 0:
        raise RuntimeError(
            f"Invalid Servix price: {price_riel}"
        )

    # زمان تجاری خود داده بازار
    business_time = data.get("businessTime")

    return {
        "source": "servix",
        "symbol": "GOLD_18_RLS",

        # قیمت اصلی API
        "price_riel": price_riel,

        # تبدیل ریال به تومان
        "price_toman": price_riel / 10,

        # زمان داده بازار
        "business_time": business_time,

        # زمان دریافت توسط سیستم ما
        "received_at": requested_at.isoformat(),

        # اطلاعات خام مفید برای دیباگ
        "raw": data,
    }


if __name__ == "__main__":
    try:
        result = get_servix_gold()

        print("================================")
        print("SERVIX GOLD 18K")
        print("================================")
        print(f"Source       : {result['source']}")
        print(f"Symbol       : {result['symbol']}")
        print(f"Price (Rial) : {result['price_riel']:,.0f}")
        print(f"Price (Toman): {result['price_toman']:,.0f}")
        print(f"BusinessTime : {result['business_time']}")
        print(f"Received At  : {result['received_at']}")
        print("================================")

    except Exception as exc:
        print("SERVIX ERROR:")
        print(exc)
