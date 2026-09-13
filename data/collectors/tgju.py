import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from database import save_tgju_price_points


# ============================================================
# CONFIG
# ============================================================

TGJU_PROFILE_URL = "https://www.tgju.org/profile/geram18"
TGJU_LIVE_URL = "https://call5.tgju.org/ajax.json"

REQUEST_TIMEOUT = 15

# فقط داده‌های اخیر CALL5 ذخیره می‌شوند.
INTRADAY_SAVE_WINDOW_HOURS = 12

# حداکثر فاصله زمانی مجاز برای یک نقطه آینده
FUTURE_TOLERANCE_MINUTES = 5

# محدوده منطقی قیمت طلای 18 عیار
#
# این فیلتر جلوی ورود داده‌هایی مثل:
# 5,000,000
# 1,042,000,000
# و سایر سری‌های اشتباه را می‌گیرد.
#
# نسبت به قیمت CALL5 محاسبه می‌شود.
MIN_PRICE_RATIO = 0.70
MAX_PRICE_RATIO = 1.30


# ============================================================
# HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": (
        "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
}


# ============================================================
# REQUEST HELPERS
# ============================================================

def fetch_url(
    url,
    referer=None,
    accept=None,
):
    headers = {
        **HEADERS,
    }

    if referer:
        headers["Referer"] = referer

    if accept:
        headers["Accept"] = accept

    response = requests.get(
        url,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response


def fetch_tgju_page():
    """
    صفحه geram18 فقط برای fallback قیمت فعلی.

    این صفحه دیگر منبع Intraday نیست.
    """

    return fetch_url(
        TGJU_PROFILE_URL,
        referer=TGJU_PROFILE_URL,
    )


# ============================================================
# CURRENT PRICE FROM PROFILE
# ============================================================

def extract_current_price(html):
    """
    استخراج قیمت فعلی از صفحه پروفایل.

    این تابع فقط fallback است.
    منبع اصلی قیمت CALL5 است.
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    text = soup.get_text(
        " ",
        strip=True,
    )

    patterns = [
        r"نرخ فعلی\s*[:：]?\s*([\d,]+)",
        r"قیمت\s*[:：]?\s*([\d,]+)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
        )

        if not match:
            continue

        try:
            price = int(
                match.group(1).replace(
                    ",",
                    "",
                )
            )

        except Exception:
            continue

        if price > 0:
            return price

    return None


# ============================================================
# TIMESTAMP
# ============================================================

def _timestamp_from_ms(
    timestamp_ms,
):
    try:
        value = float(
            timestamp_ms
        )

        if value < 10_000_000_000:
            value *= 1000

        return datetime.fromtimestamp(
            value / 1000,
            tz=timezone.utc,
        )

    except Exception:
        return None


# ============================================================
# PRICE NORMALIZATION
# ============================================================

def _normalize_price(
    value,
):
    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    if isinstance(
        value,
        (int, float),
    ):
        price = float(value)

    else:
        text = str(value)

        text = text.replace(
            ",",
            "",
        )

        text = re.sub(
            r"[^\d.]",
            "",
            text,
        )

        if not text:
            return None

        try:
            price = float(text)

        except Exception:
            return None

    if price <= 0:
        return None

    return price


# ============================================================
# LIVE PRICE FROM CALL5
# ============================================================

def fetch_live_call5():
    """
    منبع اصلی قیمت طلای 18 عیار.

    فقط:
        CALL5 -> current -> geram18

    استفاده می‌شود.

    هیچ gold-chart در این مسیر وجود ندارد.
    """

    try:
        response = requests.get(
            TGJU_LIVE_URL,
            headers={
                **HEADERS,
                "Referer": TGJU_PROFILE_URL,
                "Accept": (
                    "application/json,"
                    "text/plain,*/*"
                ),
            },
            timeout=REQUEST_TIMEOUT,
        )

        print(
            f"📡 TGJU CALL5 HTTP: "
            f"{response.status_code}",
            flush=True,
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(
            data,
            dict,
        ):
            print(
                "⚠️ CALL5: invalid JSON root.",
                flush=True,
            )

            return None

        current = data.get(
            "current",
            {},
        )

        if not isinstance(
            current,
            dict,
        ):
            print(
                "⚠️ CALL5: current is not an object.",
                flush=True,
            )

            return None

        geram18 = current.get(
            "geram18"
        )

        if not isinstance(
            geram18,
            dict,
        ):
            print(
                "⚠️ CALL5: geram18 not found.",
                flush=True,
            )

            return None

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        price_raw = (
            geram18.get("p")
            or geram18.get("price")
            or geram18.get("value")
        )

        price = _normalize_price(
            price_raw
        )

        if price is None:
            print(
                "⚠️ CALL5: invalid geram18 price.",
                flush=True,
            )

            return None

        # ----------------------------------------------------
        # TIMESTAMP
        # ----------------------------------------------------

        timestamp_ms = None

        for key in (
            "ts",
            "timestamp",
            "time",
            "t",
        ):
            value = geram18.get(
                key
            )

            if value is None:
                continue

            try:
                timestamp_ms = int(
                    float(value)
                )

                if timestamp_ms < 10_000_000_000:
                    timestamp_ms *= 1000

                break

            except Exception:
                continue

        if timestamp_ms is not None:
            timestamp = _timestamp_from_ms(
                timestamp_ms
            )

        else:
            timestamp = datetime.now(
                timezone.utc
            )

            timestamp_ms = int(
                timestamp.timestamp()
                * 1000
            )

        if timestamp is None:
            timestamp = datetime.now(
                timezone.utc
            )

            timestamp_ms = int(
                timestamp.timestamp()
                * 1000
            )

        # ----------------------------------------------------
        # TIME VALIDATION
        # ----------------------------------------------------

        now = datetime.now(
            timezone.utc
        )

        if timestamp > (
            now.timestamp()
            + (
                FUTURE_TOLERANCE_MINUTES
                * 60
            )
        ):
            print(
                "🛑 CALL5: timestamp is too far in future.",
                flush=True,
            )

            return None

        # ----------------------------------------------------
        # POINT
        # ----------------------------------------------------

        point = {
            "timestamp": timestamp,
            "timestamp_ms": timestamp_ms,
            "price": price,
        }

        print(
            "🟢 TGJU CALL5 LIVE:",
            f"{price:,.0f}",
            flush=True,
        )

        print(
            f"   timestamp={timestamp.isoformat()}",
            flush=True,
        )

        return point

    except requests.RequestException as error:
        print(
            "⚠️ TGJU CALL5 REQUEST ERROR:",
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return None

    except Exception as error:
        print(
            "⚠️ TGJU CALL5 ERROR:",
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return None


# ============================================================
# PRICE VALIDATION
# ============================================================

def validate_live_price(
    point,
):
    """
    اعتبارسنجی قیمت CALL5.

    چون CALL5 منبع اصلی است، فقط برای جلوگیری از
    داده‌های خراب یا غیرمنطقی استفاده می‌شود.
    """

    if not point:
        return False

    price = _normalize_price(
        point.get("price")
    )

    if price is None:
        print(
            "🛑 TGJU VALIDATION: invalid price.",
            flush=True,
        )

        return False

    # --------------------------------------------------------
    # قیمت 18K باید در محدوده منطقی بازار باشد.
    #
    # اینجا از یک حد مطلق محافظ هم استفاده می‌کنیم
    # تا قیمت‌های چند میلیون یا چند میلیارد وارد نشوند.
    # --------------------------------------------------------

    if price < 50_000_000:
        print(
            "🛑 TGJU VALIDATION: "
            f"price too low: {price:,.0f}",
            flush=True,
        )

        return False

    if price > 1_000_000_000:
        print(
            "🛑 TGJU VALIDATION: "
            f"price too high: {price:,.0f}",
            flush=True,
        )

        return False

    return True


# ============================================================
# SAVE INTRADAY
# ============================================================

def save_intraday_series(
    series,
):
    """
    ذخیره فقط نقاط معتبر CALL5.

    این تابع دیگر هیچ chart series را ذخیره نمی‌کند.
    """

    if not series:
        print(
            "⚠️ TGJU: no valid CALL5 point to save.",
            flush=True,
        )

        return {
            "received": 0,
            "saved": 0,
            "duplicates": 0,
        }

    safe_series = []

    now = datetime.now(
        timezone.utc
    )

    window_start = (
        now.timestamp()
        - (
            INTRADAY_SAVE_WINDOW_HOURS
            * 3600
        )
    )

    for point in series:

        if not validate_live_price(
            point
        ):
            continue

        timestamp = point.get(
            "timestamp"
        )

        if timestamp is None:
            continue

        timestamp_seconds = (
            timestamp.timestamp()
        )

        # ----------------------------------------------------
        # Reject old data
        # ----------------------------------------------------

        if timestamp_seconds < window_start:
            continue

        # ----------------------------------------------------
        # Reject future data
        # ----------------------------------------------------

        if timestamp_seconds > (
            now.timestamp()
            + (
                FUTURE_TOLERANCE_MINUTES
                * 60
            )
        ):
            continue

        safe_series.append(
            point
        )

    if not safe_series:
        print(
            "🛑 TGJU: CALL5 point rejected.",
            flush=True,
        )

        return {
            "received": len(series),
            "saved": 0,
            "duplicates": 0,
        }

    # --------------------------------------------------------
    # Deduplicate timestamps
    # --------------------------------------------------------

    unique = {}

    for point in safe_series:

        timestamp_ms = point.get(
            "timestamp_ms"
        )

        if timestamp_ms is None:
            continue

        unique[
            timestamp_ms
        ] = point

    safe_series = list(
        unique.values()
    )

    safe_series.sort(
        key=lambda item: item[
            "timestamp_ms"
        ]
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    result = save_tgju_price_points(
        safe_series,
        symbol="gold_18k",
    )

    print(
        "💾 TGJU RAW INTRADAY:",
        f"received={len(safe_series)}",
        f"saved={result['saved']}",
        f"duplicates={result['duplicates']}",
        flush=True,
    )

    return result


# ============================================================
# DIAGNOSTIC
# ============================================================

def print_series_diagnostic(
    series,
):
    """
    Diagnostic برای سری واقعی CALL5.
    """

    print(
        "",
        flush=True,
    )

    print(
        "🕯️ TGJU CALL5 INTRADAY DIAGNOSTIC",
        flush=True,
    )

    print(
        "-" * 70,
        flush=True,
    )

    if not series:
        print(
            "❌ No CALL5 intraday series.",
            flush=True,
        )

        print(
            "-" * 70,
            flush=True,
        )

        return

    print(
        f"📊 TOTAL POINTS: {len(series)}",
        flush=True,
    )

    first = series[0]
    last = series[-1]

    print(
        f"🕐 FIRST: "
        f"{first['timestamp'].isoformat()} "
        f"| {first['price']:,.0f}",
        flush=True,
    )

    print(
        f"🕐 LAST : "
        f"{last['timestamp'].isoformat()} "
        f"| {last['price']:,.0f}",
        flush=True,
    )

    print(
        "",
        flush=True,
    )

    print(
        "📈 LAST POINT:",
        f"{last['price']:,.0f} تومان",
        flush=True,
    )

    print(
        "-" * 70,
        flush=True,
    )


# ============================================================
# MAIN
# ============================================================

def get_gold_18k():
    """
    دریافت طلای 18 عیار.

    معماری جدید:

        CALL5
          ↓
        geram18
          ↓
        validate
          ↓
        database
          ↓
        Candle Engine

    gold-chart عمداً از این مسیر حذف شده است.
    """

    try:

        print(
            "📡 TGJU: requesting gold data...",
            flush=True,
        )

        # ====================================================
        # 1. CALL5
        # منبع اصلی و唯一 Intraday
        # ====================================================

        live_point = fetch_live_call5()

        # ====================================================
        # 2. FALLBACK PROFILE
        # فقط اگر CALL5 در دسترس نبود
        # ====================================================

        profile_price = None

        if live_point is None:

            print(
                "⚠️ TGJU: CALL5 unavailable.",
                flush=True,
            )

            print(
                "📡 TGJU: requesting profile fallback...",
                flush=True,
            )

            profile_response = fetch_tgju_page()

            print(
                f"🌐 TGJU PROFILE HTTP: "
                f"{profile_response.status_code}",
                flush=True,
            )

            try:
                profile_price = extract_current_price(
                    profile_response.text
                )

            except Exception as error:
                print(
                    "⚠️ TGJU PROFILE FALLBACK ERROR:",
                    repr(error),
                    flush=True,
                )

        # ====================================================
        # 3. DETERMINE CURRENT PRICE
        # ====================================================

        if live_point is not None:

            price = int(
                live_point["price"]
            )

        elif profile_price is not None:

            price = int(
                profile_price
            )

            # Profile fallback فقط قیمت فعلی می‌دهد.
            # برای intraday نقطه فعلی می‌سازیم.

            timestamp = datetime.now(
                timezone.utc
            )

            live_point = {
                "timestamp": timestamp,
                "timestamp_ms": int(
                    timestamp.timestamp()
                    * 1000
                ),
                "price": float(
                    price
                ),
            }

        else:

            raise RuntimeError(
                "Could not obtain current "
                "TGJU 18K gold price."
            )

        # ====================================================
        # 4. VALIDATE
        # ====================================================

        if not validate_live_price(
            live_point
        ):
            raise RuntimeError(
                "TGJU 18K price failed validation."
            )

        # ====================================================
        # 5. ONLY ONE INTRADAY POINT
        # ====================================================

        intraday_series = [
            live_point
        ]

        print(
            "",
            flush=True,
        )

        print(
            "🕯️ TGJU FINAL INTRADAY SERIES:",
            flush=True,
        )

        print(
            "   source=CALL5",
            flush=True,
        )

        print(
            f"   total points={len(intraday_series)}",
            flush=True,
        )

        print(
            f"   timestamp="
            f"{live_point['timestamp'].isoformat()}",
            flush=True,
        )

        print(
            f"   price="
            f"{live_point['price']:,.0f}",
            flush=True,
        )

        # ====================================================
        # 6. SAVE
        # ====================================================

        save_result = save_intraday_series(
            intraday_series
        )

        # ====================================================
        # 7. DIAGNOSTIC
        # ====================================================

        print_series_diagnostic(
            intraday_series
        )

        # ====================================================
        # 8. RESULT
        # ====================================================

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        print(
            "",
            flush=True,
        )

        print(
            f"🟢 TGJU: "
            f"{price:,.0f} تومان",
            flush=True,
        )

        print(
            "📊 TGJU CHART POINTS: 0",
            flush=True,
        )

        print(
            "📡 TGJU INTRADAY SOURCE: CALL5",
            flush=True,
        )

        print(
            f"💾 TGJU SAVED: "
            f"{save_result['saved']}",
            flush=True,
        )

        return {
            "symbol": "gold_18k",
            "price": price,
            "currency": "IRR",
            "timestamp": timestamp,
            "source": "tgju",
            "series": intraday_series,
        }

    except requests.RequestException as error:

        print(
            "🔴 TGJU REQUEST ERROR:",
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        raise

    except Exception as error:

        print(
            "🔴 TGJU ERROR:",
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        raise
