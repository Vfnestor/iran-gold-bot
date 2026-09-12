import os
import requests
from datetime import datetime, timezone


SERVIX_URL = "https://servix.cc/api/v1/assets/GOLD_18_RLS"


def get_servix_api_key():
    """
    دریافت API Key در زمان اجرای تابع.

    این کار باعث می‌شود اگر .env بعداً load شده باشد،
    API Key از دست نرود.
    """

    api_key = os.getenv("SERVIX_API_KEY")

    if not api_key:
        raise RuntimeError(
            "SERVIX_API_KEY environment variable is not set"
        )

    return api_key


def get_servix_gold():
    """
    دریافت آخرین قیمت طلای 18 عیار از Servix.

    Servix:
        price_riel  -> قیمت بر حسب ریال
        price_toman -> قیمت بر حسب تومان

    این تابع:
        - خطای 429 را تشخیص می‌دهد
        - Retry خودکار انجام نمی‌دهد
        - زمان درخواست را ثبت می‌کند
        - اطلاعات کامل پاسخ را برمی‌گرداند
    """

    api_key = get_servix_api_key()

    headers = {
        "X-API-Key": api_key,
        "Accept": "application/json",
    }

    requested_at = datetime.now(timezone.utc)

    try:

        response = requests.get(
            SERVIX_URL,
            headers=headers,
            timeout=10,
        )

    except requests.Timeout as exc:

        raise RuntimeError(
            "Servix request timed out"
        ) from exc

    except requests.ConnectionError as exc:

        raise RuntimeError(
            "Servix connection failed"
        ) from exc

    except requests.RequestException as exc:

        raise RuntimeError(
            f"Servix request failed: {exc}"
        ) from exc


    # ========================================================
    # RATE LIMIT
    # ========================================================

    if response.status_code == 429:

        retry_after = response.headers.get(
            "Retry-After"
        )

        message = (
            "Servix rate limit reached "
            "(HTTP 429)"
        )

        if retry_after:

            message += (
                f". Retry-After: "
                f"{retry_after}"
            )

        raise RuntimeError(
            message
        )


    # ========================================================
    # OTHER HTTP ERRORS
    # ========================================================

    try:

        response.raise_for_status()

    except requests.HTTPError as exc:

        raise RuntimeError(
            f"Servix HTTP error "
            f"{response.status_code}: {exc}"
        ) from exc


    # ========================================================
    # JSON
    # ========================================================

    try:

        data = response.json()

    except ValueError as exc:

        raise RuntimeError(
            "Servix returned invalid JSON"
        ) from exc


    # ========================================================
    # RESPONSE VALIDATION
    # ========================================================

    if not isinstance(data, dict):

        raise RuntimeError(
            "Unexpected Servix response type: "
            f"{type(data).__name__}"
        )


    # ========================================================
    # ASSET CODE
    # ========================================================

    if data.get("code") != "GOLD_18_RLS":

        raise RuntimeError(
            "Unexpected Servix asset code: "
            f"{data.get('code')}"
        )


    # ========================================================
    # PRICE
    # ========================================================

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


    # ========================================================
    # BUSINESS TIME
    # ========================================================

    business_time = data.get(
        "businessTime"
    )


    # ========================================================
    # TOMAN CONVERSION
    # ========================================================

    price_toman = price_riel / 10


    # ========================================================
    # RESULT
    # ========================================================

    return {

        "source":
            "servix",

        "symbol":
            "GOLD_18_RLS",

        # قیمت اصلی Servix
        "price_riel":
            price_riel,

        # قیمت استاندارد پروژه
        "price_toman":
            price_toman,

        # زمان بازار
        "business_time":
            business_time,

        # زمان دریافت توسط ربات
        "received_at":
            requested_at.isoformat(),

        # HTTP status
        "http_status":
            response.status_code,

        # داده خام
        "raw":
            data,
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    try:

        result = get_servix_gold()

        print(
            "================================"
        )

        print(
            "SERVIX GOLD 18K"
        )

        print(
            "================================"
        )

        print(
            f"Source       : "
            f"{result['source']}"
        )

        print(
            f"Symbol       : "
            f"{result['symbol']}"
        )

        print(
            f"Price (Rial) : "
            f"{result['price_riel']:,.0f}"
        )

        print(
            f"Price (Toman): "
            f"{result['price_toman']:,.0f}"
        )

        print(
            f"BusinessTime : "
            f"{result['business_time']}"
        )

        print(
            f"Received At  : "
            f"{result['received_at']}"
        )

        print(
            f"HTTP Status  : "
            f"{result['http_status']}"
        )

        print(
            "================================"
        )

    except Exception as exc:

        print(
            "SERVIX ERROR:"
        )

        print(
            exc
        )
