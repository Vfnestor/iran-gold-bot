import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from database import save_tgju_price_points


# ============================================================
# CONFIG
# ============================================================

TGJU_PROFILE_URL = "https://www.tgju.org/profile/geram18"
TGJU_CHART_URL = "https://www.tgju.org/gold-chart"
TGJU_LIVE_URL = "https://call5.tgju.org/ajax.json"

REQUEST_TIMEOUT = 15

# فقط داده‌های intraday اخیر ذخیره می‌شوند.
# تاریخچه‌های قدیمی profile/geram18 وارد موتور کندل نمی‌شوند.
INTRADAY_SAVE_WINDOW_HOURS = 12

# اگر فاصله بین دو نقطه بیشتر از این باشد،
# آن‌ها را یک سری پیوسته در نظر نمی‌گیریم.
MAX_INTRADAY_GAP_SECONDS = 30 * 60

# حداقل نقاط قابل قبول برای سری intraday
MIN_INTRADAY_POINTS = 2

# حداکثر فاصله آینده مجاز نسبت به ساعت سرور
FUTURE_TOLERANCE_MINUTES = 5


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

def fetch_url(url, referer=None, accept=None):
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
    return fetch_url(
        TGJU_PROFILE_URL,
        referer=TGJU_PROFILE_URL,
    )


def fetch_tgju_gold_chart():
    print(
        "📡 TGJU CHART: requesting gold-chart...",
        flush=True,
    )

    response = fetch_url(
        TGJU_CHART_URL,
        referer=TGJU_PROFILE_URL,
    )

    print(
        f"🌐 TGJU GOLD-CHART HTTP: "
        f"{response.status_code} "
        f"| size={len(response.content):,}",
        flush=True,
    )

    return response


# ============================================================
# CURRENT PRICE FROM PROFILE
# ============================================================

def extract_current_price(html):
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

        price = int(
            match.group(1).replace(
                ",",
                "",
            )
        )

        if price > 0:
            return price

    raise RuntimeError(
        "Could not find 18K gold price on TGJU profile."
    )


# ============================================================
# LIVE PRICE FROM CALL5
# ============================================================

def fetch_live_call5():
    try:
        response = requests.get(
            TGJU_LIVE_URL,
            headers={
                **HEADERS,
                "Referer": TGJU_PROFILE_URL,
                "Accept": "application/json,text/plain,*/*",
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

        current = data.get(
            "current",
            {},
        )

        geram18 = current.get(
            "geram18"
        )

        if not geram18:
            print(
                "⚠️ CALL5: geram18 not found.",
                flush=True,
            )
            return None

        price_raw = (
            geram18.get("p")
            or geram18.get("price")
            or geram18.get("value")
        )

        if price_raw is None:
            print(
                "⚠️ CALL5: price field not found.",
                flush=True,
            )
            return None

        price_text = str(
            price_raw
        )

        price_text = re.sub(
            r"[^\d.]",
            "",
            price_text,
        )

        if not price_text:
            return None

        price = float(
            price_text
        )

        if price <= 0:
            return None

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

        if timestamp_ms:
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

    except Exception as error:
        print(
            "⚠️ TGJU CALL5 ERROR:",
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return None


# ============================================================
# TIMESTAMP
# ============================================================

def _timestamp_from_ms(timestamp_ms):
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

def _normalize_price(value):
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
# TIMESTAMP VALIDATION
# ============================================================

def _looks_like_timestamp(value):
    try:
        number = float(
            value
        )

    except Exception:
        return False

    return (
        1_000_000_000
        <= number
        <= 2_000_000_000_000
    )


# ============================================================
# GENERIC JSON POINT EXTRACTION
# ============================================================

def _extract_points_from_json(data):
    points = []

    def add_point(
        timestamp_value,
        price_value,
    ):
        if not _looks_like_timestamp(
            timestamp_value
        ):
            return

        price = _normalize_price(
            price_value
        )

        if price is None:
            return

        timestamp = _timestamp_from_ms(
            timestamp_value
        )

        if timestamp is None:
            return

        now = datetime.now(
            timezone.utc
        )

        if timestamp > (
            now
            + timedelta(
                minutes=FUTURE_TOLERANCE_MINUTES
            )
        ):
            return

        if timestamp < (
            now
            - timedelta(
                days=30
            )
        ):
            return

        timestamp_ms = int(
            timestamp.timestamp()
            * 1000
        )

        points.append(
            {
                "timestamp": timestamp,
                "timestamp_ms": timestamp_ms,
                "price": price,
            }
        )

    def walk(obj):
        if isinstance(
            obj,
            dict,
        ):
            timestamp_keys = (
                "timestamp",
                "timestamp_ms",
                "time",
                "ts",
                "t",
                "date",
                "datetime",
            )

            price_keys = (
                "price",
                "p",
                "value",
                "close",
                "c",
                "last",
                "rate",
            )

            timestamp_value = None
            price_value = None

            for key in timestamp_keys:
                if key not in obj:
                    continue

                candidate = obj.get(
                    key
                )

                if _looks_like_timestamp(
                    candidate
                ):
                    timestamp_value = candidate
                    break

            for key in price_keys:
                if key not in obj:
                    continue

                candidate = obj.get(
                    key
                )

                if (
                    _normalize_price(
                        candidate
                    )
                    is not None
                ):
                    price_value = candidate
                    break

            if (
                timestamp_value is not None
                and price_value is not None
            ):
                add_point(
                    timestamp_value,
                    price_value,
                )

            for value in obj.values():
                walk(
                    value
                )

        elif isinstance(
            obj,
            list,
        ):
            if len(obj) >= 2:
                first = obj[0]
                second = obj[1]

                if (
                    _looks_like_timestamp(
                        first
                    )
                    and _normalize_price(
                        second
                    )
                    is not None
                ):
                    add_point(
                        first,
                        second,
                    )

            for item in obj:
                walk(
                    item
                )

    walk(
        data
    )

    unique = {}

    for point in points:
        unique[
            point["timestamp_ms"]
        ] = point

    result = list(
        unique.values()
    )

    result.sort(
        key=lambda item: item[
            "timestamp_ms"
        ]
    )

    return result


# ============================================================
# CHART DATA EXTRACTION
# ============================================================

def extract_price_series(html):
    """
    استخراج سری‌های chartData از صفحه gold-chart.

    نکته مهم:
    profile/geram18 ممکن است chartData بسیار قدیمی داشته باشد.
    این تابع فقط روی gold-chart استفاده می‌شود.
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidate_series = []

    now = datetime.now(
        timezone.utc
    )

    for script_index, script in enumerate(
        soup.find_all("script")
    ):
        if script.get("src"):
            continue

        script_text = script.string

        if not script_text:
            script_text = script.get_text()

        if not script_text:
            continue

        if "chartData" not in script_text:
            continue

        positions = [
            match.start()
            for match in re.finditer(
                r"chartData\s*:",
                script_text,
                flags=re.IGNORECASE,
            )
        ]

        for chart_index, position in enumerate(
            positions
        ):
            section = script_text[
                position:
                position + 500000
            ]

            matches = re.findall(
                r"\[\s*(\d{12,13})\s*,\s*([\d.]+)\s*\]",
                section,
            )

            if not matches:
                continue

            points = []

            for timestamp_raw, price_raw in matches:
                timestamp = _timestamp_from_ms(
                    timestamp_raw
                )

                price = _normalize_price(
                    price_raw
                )

                if timestamp is None:
                    continue

                if price is None:
                    continue

                if timestamp > (
                    now
                    + timedelta(
                        minutes=FUTURE_TOLERANCE_MINUTES
                    )
                ):
                    continue

                points.append(
                    {
                        "timestamp": timestamp,
                        "timestamp_ms": int(
                            timestamp.timestamp()
                            * 1000
                        ),
                        "price": price,
                    }
                )

            if len(points) < 2:
                continue

            unique = {}

            for point in points:
                unique[
                    point["timestamp_ms"]
                ] = point

            cleaned = list(
                unique.values()
            )

            cleaned.sort(
                key=lambda item: item[
                    "timestamp_ms"
                ]
            )

            candidate_series.append(
                {
                    "script_index": script_index,
                    "chart_index": chart_index,
                    "points": cleaned,
                }
            )

    if not candidate_series:
        print(
            "❌ TGJU GOLD-CHART: "
            "no chartData series found.",
            flush=True,
        )

        return []

    candidate_series.sort(
        key=lambda candidate: (
            candidate["points"][-1][
                "timestamp_ms"
            ],
            len(candidate["points"]),
        ),
        reverse=True,
    )

    print(
        "",
        flush=True,
    )

    print(
        "🔎 TGJU GOLD-CHART CANDIDATES:",
        len(candidate_series),
        flush=True,
    )

    print(
        "-" * 70,
        flush=True,
    )

    for index, candidate in enumerate(
        candidate_series,
        start=1,
    ):
        points = candidate["points"]

        print(
            f"   #{index} "
            f"| points={len(points)} "
            f"| first={points[0]['timestamp'].isoformat()} "
            f"| last={points[-1]['timestamp'].isoformat()}",
            flush=True,
        )

    print(
        "-" * 70,
        flush=True,
    )

    best = candidate_series[0]["points"]

    print(
        "✅ TGJU GOLD-CHART SELECTED SERIES:",
        flush=True,
    )

    print(
        f"   points={len(best)}",
        flush=True,
    )

    print(
        f"   first={best[0]['timestamp'].isoformat()}",
        flush=True,
    )

    print(
        f"   last={best[-1]['timestamp'].isoformat()}",
        flush=True,
    )

    return best


# ============================================================
# DISCOVER CHART DATA FROM GOLD-CHART
# ============================================================

def extract_gold_chart_series(html):
    """
    gold-chart منبع اصلی intraday است.

    اول chartData مستقیم صفحه را بررسی می‌کنیم.
    سپس اگر صفحه JSON داشته باشد، آن را نیز بررسی می‌کنیم.
    """

    # --------------------------------------------------------
    # 1. chartData داخل HTML
    # --------------------------------------------------------

    series = extract_price_series(
        html
    )

    if series:
        return series

    # --------------------------------------------------------
    # 2. تلاش برای JSON مستقیم
    # --------------------------------------------------------

    try:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        text = soup.get_text(
            " ",
            strip=True,
        )

        if text.startswith(
            ("{", "[")
        ):
            data = None

            try:
                import json

                data = json.loads(
                    text
                )

            except Exception:
                data = None

            if data is not None:
                points = _extract_points_from_json(
                    data
                )

                if points:
                    return points

    except Exception:
        pass

    return []


# ============================================================
# FILTER REAL INTRADAY DATA
# ============================================================

def extract_recent_intraday_points(
    series,
):
    if not series:
        return []

    now = datetime.now(
        timezone.utc
    )

    window_start = (
        now
        - timedelta(
            hours=INTRADAY_SAVE_WINDOW_HOURS
        )
    )

    recent = [
        point
        for point in series
        if (
            window_start
            <= point["timestamp"]
            <= now
            + timedelta(
                minutes=FUTURE_TOLERANCE_MINUTES
            )
        )
    ]

    if len(recent) < MIN_INTRADAY_POINTS:
        print(
            "",
            flush=True,
        )

        print(
            "⚠️ TGJU INTRADAY FILTER:",
            flush=True,
        )

        print(
            f"   source points={len(series)}",
            flush=True,
        )

        print(
            f"   recent points={len(recent)}",
            flush=True,
        )

        print(
            "   ❌ Not enough recent points.",
            flush=True,
        )

        return []

    recent.sort(
        key=lambda item: item[
            "timestamp_ms"
        ]
    )

    # --------------------------------------------------------
    # Build continuous segments
    # --------------------------------------------------------

    segments = []

    current_segment = [
        recent[0]
    ]

    for previous, current in zip(
        recent[:-1],
        recent[1:],
    ):
        delta = (
            current["timestamp_ms"]
            - previous["timestamp_ms"]
        ) / 1000

        if (
            delta > 0
            and delta <= MAX_INTRADAY_GAP_SECONDS
        ):
            current_segment.append(
                current
            )

        else:
            if (
                len(current_segment)
                >= MIN_INTRADAY_POINTS
            ):
                segments.append(
                    current_segment
                )

            current_segment = [
                current
            ]

    if (
        len(current_segment)
        >= MIN_INTRADAY_POINTS
    ):
        segments.append(
            current_segment
        )

    if not segments:
        print(
            "⚠️ TGJU: "
            "recent points are not continuous.",
            flush=True,
        )

        return []

    # مهم:
    # طولانی‌ترین سری را انتخاب می‌کنیم،
    # نه صرفاً آخرین تک نقطه.
    selected = max(
        segments,
        key=lambda segment: (
            len(segment),
            segment[-1]["timestamp_ms"],
        ),
    )

    print(
        "",
        flush=True,
    )

    print(
        "✅ REAL TGJU INTRADAY SERIES:",
        flush=True,
    )

    print(
        f"   points={len(selected)}",
        flush=True,
    )

    print(
        f"   first={selected[0]['timestamp'].isoformat()}",
        flush=True,
    )

    print(
        f"   last={selected[-1]['timestamp'].isoformat()}",
        flush=True,
    )

    intervals = []

    for previous, current in zip(
        selected[:-1],
        selected[1:],
    ):
        delta = (
            current["timestamp_ms"]
            - previous["timestamp_ms"]
        ) / 1000

        if delta > 0:
            intervals.append(
                delta
            )

    if intervals:
        print(
            f"   avg interval="
            f"{sum(intervals) / len(intervals):.2f}s",
            flush=True,
        )

        print(
            f"   min interval="
            f"{min(intervals):.2f}s",
            flush=True,
        )

        print(
            f"   max interval="
            f"{max(intervals):.2f}s",
            flush=True,
        )

    return selected


# ============================================================
# MERGE POINTS
# ============================================================

def merge_points(*series_list):
    unique = {}

    for series in series_list:
        if not series:
            continue

        for point in series:
            timestamp_ms = point.get(
                "timestamp_ms"
            )

            if not timestamp_ms:
                continue

            unique[
                timestamp_ms
            ] = point

    result = list(
        unique.values()
    )

    result.sort(
        key=lambda item: item[
            "timestamp_ms"
        ]
    )

    return result


# ============================================================
# SAVE INTRADAY
# ============================================================

def save_intraday_series(
    series,
):
    if not series:
        print(
            "⚠️ TGJU: "
            "no intraday data to save.",
            flush=True,
        )

        return {
            "received": 0,
            "saved": 0,
            "duplicates": 0,
        }

    safe_series = extract_recent_intraday_points(
        series
    )

    if not safe_series:
        print(
            "🛑 TGJU: "
            "intraday data rejected.",
            flush=True,
        )

        return {
            "received": len(series),
            "saved": 0,
            "duplicates": 0,
        }

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
    print(
        "",
        flush=True,
    )

    print(
        "🕯️ TGJU INTRADAY SERIES DIAGNOSTIC",
        flush=True,
    )

    print(
        "-" * 70,
        flush=True,
    )

    if not series:
        print(
            "❌ No intraday series.",
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

    print(
        f"🕐 FIRST: "
        f"{series[0]['timestamp'].isoformat()} "
        f"| {series[0]['price']:,.0f}",
        flush=True,
    )

    print(
        f"🕐 LAST : "
        f"{series[-1]['timestamp'].isoformat()} "
        f"| {series[-1]['price']:,.0f}",
        flush=True,
    )

    print(
        "",
        flush=True,
    )

    print(
        "📈 LAST 10 POINTS:",
        flush=True,
    )

    for point in series[-10:]:
        print(
            f"   {point['timestamp'].isoformat()} "
            f"| {point['price']:,.0f}",
            flush=True,
        )

    intervals = []

    for previous, current in zip(
        series[:-1],
        series[1:],
    ):
        delta = (
            current["timestamp_ms"]
            - previous["timestamp_ms"]
        ) / 1000

        if delta > 0:
            intervals.append(
                delta
            )

    if intervals:
        print(
            "",
            flush=True,
        )

        print(
            f"⏱️ AVG INTERVAL: "
            f"{sum(intervals) / len(intervals):.2f}s",
            flush=True,
        )

        print(
            f"⏱️ MIN INTERVAL: "
            f"{min(intervals):.2f}s",
            flush=True,
        )

        print(
            f"⏱️ MAX INTERVAL: "
            f"{max(intervals):.2f}s",
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
    try:
        print(
            "📡 TGJU: requesting gold data...",
            flush=True,
        )

        # ====================================================
        # 1. PROFILE
        # فقط برای fallback قیمت
        # ====================================================

        profile_response = fetch_tgju_page()

        print(
            f"🌐 TGJU PROFILE HTTP: "
            f"{profile_response.status_code}",
            flush=True,
        )

        profile_html = profile_response.text

        try:
            profile_price = extract_current_price(
                profile_html
            )
        except Exception:
            profile_price = None

        # ====================================================
        # 2. CALL5
        # قیمت لحظه‌ای اصلی
        # ====================================================

        live_point = fetch_live_call5()

        if live_point:
            price = int(
                live_point["price"]
            )
        elif profile_price:
            price = int(
                profile_price
            )
        else:
            raise RuntimeError(
                "Could not obtain current TGJU gold price."
            )

        # ====================================================
        # 3. GOLD-CHART
        # منبع اصلی intraday
        # ====================================================

        chart_response = fetch_tgju_gold_chart()

        chart_html = chart_response.text

        chart_series = extract_gold_chart_series(
            chart_html
        )

        print_series_diagnostic(
            chart_series
        )

        # ====================================================
        # 4. ADD LIVE POINT
        # ====================================================

        combined = merge_points(
            chart_series,
            [live_point]
            if live_point
            else [],
        )

        print(
            "",
            flush=True,
        )

        print(
            "🕯️ TGJU FINAL INTRADAY SERIES:",
            flush=True,
        )

        print(
            f"   total points={len(combined)}",
            flush=True,
        )

        if combined:
            print(
                f"   first="
                f"{combined[0]['timestamp'].isoformat()}",
                flush=True,
            )

            print(
                f"   last="
                f"{combined[-1]['timestamp'].isoformat()}",
                flush=True,
            )

        # ====================================================
        # 5. SAVE
        # ====================================================

        save_result = save_intraday_series(
            combined
        )

        # ====================================================
        # 6. RESULT
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
            f"📊 TGJU CHART POINTS: "
            f"{len(chart_series)}",
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
            "series": combined,
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
