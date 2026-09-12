import os
import requests
from datetime import datetime, timezone

from database import (
    reserve_servix_request,
    get_servix_usage,
)


SERVIX_URL = (
    "https://servix.cc/api/v1/assets/GOLD_18_RLS"
)


def get_servix_api_key():
    """
    دریافت API Key در زمان اجرای تابع.
    """

    api_key = os.getenv(
        "SERVIX_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "SERVIX_API_KEY environment variable "
            "is not set"
        )

    return api_key


def get_servix_gold():
    """
    دریافت آخرین قیمت طلای 18 عیار از Servix.

    محدودیت داخلی پروژه:
        حداکثر 45 درخواست در روز

    Servix:
        price_riel  -> ریال
        price_toman -> تومان
    """

    # ========================================================
    # CHECK / RESERVE DAILY QUOTA
    # ========================================================

    quota = reserve_servix_request()

    if not quota["allowed"]:

        raise RuntimeError(
            "Servix daily request quota exhausted. "
            f"Used: {quota['used']}, "
            f"Limit: {45}, "
            f"Date: {quota['date']}"
        )


    print(
        "📡 Servix quota reserved: "
        f"{quota['used']}/45 "
        f"(remaining: {quota['remaining']})",
        flush=True
    )


    # ========================================================
    # API KEY
    # ========================================================

    api_key = get_servix_api_key()


    headers = {

        "X-API-Key":
            api_key,

        "Accept":
            "application/json",
    }


    requested_at = datetime.now(
        timezone.utc
    )


    # ========================================================
    # HTTP REQUEST
    # ========================================================

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

        retry_after = (
            response.headers.get(
                "Retry-After"
            )
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

    value = data.get(
        "value"
    )


    if value is None:

        raise RuntimeError(
            "Servix response does not contain "
            "'value'"
        )


    try:

        price_riel = float(
            value
        )

    except (
        TypeError,
        ValueError
    ) as exc:

        raise RuntimeError(
            f"Invalid Servix price value: "
            f"{value}"
        ) from exc


    if price_riel <= 0:

        raise RuntimeError(
            f"Invalid Servix price: "
            f"{price_riel}"
        )


    # ========================================================
    # BUSINESS TIME
    # ========================================================

    business_time = data.get(
        "businessTime"
    )


    # ========================================================
    # TOMAN
    # ========================================================

    price_toman = (
        price_riel / 10
    )


    # ========================================================
    # RESULT
    # ========================================================

    return {

        "source":
            "servix",

        "symbol":
            "GOLD_18_RLS",

        "price_riel":
            price_riel,

        "price_toman":
            price_toman,

        "business_time":
            business_time,

        "received_at":
            requested_at.isoformat(),

        "http_status":
            response.status_code,

        "raw":
            data,

        "quota":
            quota,
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "SERVIX TEST"
    )

    print(
        "================================"
    )


    try:

        # ----------------------------------------------------
        # نمایش سهمیه قبل از درخواست
        # ----------------------------------------------------

        usage_before = get_servix_usage()

        print(
            "📊 QUOTA BEFORE REQUEST"
        )

        print(
            f"Date      : "
            f"{usage_before['date']}"
        )

        print(
            f"Used      : "
            f"{usage_before['used']}"
        )

        print(
            f"Remaining : "
            f"{usage_before['remaining']}"
        )

        print(
            f"Limit     : "
            f"{usage_before['limit']}"
        )


        # ----------------------------------------------------
        # درخواست Servix
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # سهمیه بعد از درخواست
        # ----------------------------------------------------

        usage_after = get_servix_usage()

        print(
            "📊 QUOTA AFTER REQUEST"
        )

        print(
            f"Used      : "
            f"{usage_after['used']}"
        )

        print(
            f"Remaining : "
            f"{usage_after['remaining']}"
        )


    except Exception as exc:

        print(
            "SERVIX ERROR:"
        )

        print(
            exc
        )
