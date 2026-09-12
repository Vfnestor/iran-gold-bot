import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

TGJU_URL = "https://www.tgju.org/profile/geram18"

REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/131.0 Safari/537.36"
    )
}


# ============================================================
# REQUEST
# ============================================================

def fetch_tgju_page():

    response = requests.get(
        TGJU_URL,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response


# ============================================================
# CURRENT PRICE
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

    match = re.search(
        r"نرخ فعلی\s*[:：]?\s*([\d,]+)",
        text,
    )

    if not match:

        raise RuntimeError(
            "Could not find 18K gold price on TGJU."
        )

    price = int(
        match.group(1).replace(",", "")
    )

    if price <= 0:

        raise RuntimeError(
            "Invalid TGJU gold price."
        )

    return price


# ============================================================
# FIND TGJU PRICE SERIES
# ============================================================

def extract_price_series(html):

    """
    TGJU chart data appears in the page as pairs:

        [timestamp_ms, price]

    Example:

        [1789215616000, 240895000]

    This function extracts candidate intraday series
    from inline JavaScript.
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidate_series = []

    # --------------------------------------------------------
    # Inspect inline JavaScript
    # --------------------------------------------------------

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

        # ----------------------------------------------------
        # Only inspect scripts containing chart data
        # ----------------------------------------------------

        if "chartData" not in script_text:
            continue

        if "msHighcharts" not in script_text:
            continue

        # ----------------------------------------------------
        # Find chartData sections
        # ----------------------------------------------------

        chart_positions = [
            match.start()
            for match in re.finditer(
                r"chartData\s*:",
                script_text,
                flags=re.IGNORECASE,
            )
        ]

        for position in chart_positions:

            section = script_text[
                position:
                position + 500000
            ]

            # ------------------------------------------------
            # Extract timestamp / price pairs
            # ------------------------------------------------

            matches = re.findall(
                r"\[\s*(\d{12,13})\s*,\s*([\d.]+)\s*\]",
                section,
            )

            if not matches:
                continue

            points = []

            for timestamp_raw, price_raw in matches:

                try:

                    timestamp_ms = int(
                        timestamp_raw
                    )

                    price = float(
                        price_raw
                    )

                except ValueError:
                    continue

                # --------------------------------------------
                # Basic validation
                # --------------------------------------------

                if timestamp_ms <= 0:
                    continue

                if price <= 0:
                    continue

                timestamp = datetime.fromtimestamp(
                    timestamp_ms / 1000,
                    tz=timezone.utc,
                )

                points.append(
                    {
                        "timestamp": timestamp,
                        "timestamp_ms": timestamp_ms,
                        "price": price,
                    }
                )

            if len(points) >= 5:

                candidate_series.append(
                    points
                )

    # ========================================================
    # Select best candidate
    # ========================================================

    if not candidate_series:

        return []

    # طولانی‌ترین سری معمولاً سری اصلی نمودار است.
    best_series = max(
        candidate_series,
        key=len,
    )

    # --------------------------------------------------------
    # Remove duplicate timestamps
    # --------------------------------------------------------

    unique = {}

    for point in best_series:

        unique[
            point["timestamp_ms"]
        ] = point

    result = list(
        unique.values()
    )

    result.sort(
        key=lambda x: x["timestamp_ms"]
    )

    return result


# ============================================================
# PRINT SERIES DIAGNOSTIC
# ============================================================

def print_series_diagnostic(series):

    print(
        "",
        flush=True,
    )

    print(
        "🕯️ TGJU INTRADAY SERIES",
        flush=True,
    )

    print(
        "-" * 60,
        flush=True,
    )

    if not series:

        print(
            "❌ No TGJU price series found.",
            flush=True,
        )

        print(
            "-" * 60,
            flush=True,
        )

        return

    print(
        f"📊 POINTS FOUND: {len(series)}",
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
        "📈 LAST 10 POINTS:",
        flush=True,
    )

    for point in series[-10:]:

        print(
            f"   {point['timestamp'].isoformat()} "
            f"| {point['price']:,.0f}",
            flush=True,
        )

    print(
        "",
        flush=True,
    )

    # --------------------------------------------------------
    # Estimate sampling interval
    # --------------------------------------------------------

    intervals = []

    for previous, current in zip(
        series[-50:-1],
        series[-49:],
    ):

        delta = (
            current["timestamp_ms"]
            - previous["timestamp_ms"]
        )

        if delta > 0:

            intervals.append(
                delta / 1000
            )

    if intervals:

        average_interval = (
            sum(intervals)
            / len(intervals)
        )

        print(
            f"⏱️ AVG SAMPLE INTERVAL: "
            f"{average_interval:.2f} sec",
            flush=True,
        )

        print(
            f"⏱️ MIN SAMPLE INTERVAL: "
            f"{min(intervals):.2f} sec",
            flush=True,
        )

        print(
            f"⏱️ MAX SAMPLE INTERVAL: "
            f"{max(intervals):.2f} sec",
            flush=True,
        )

    print(
        "-" * 60,
        flush=True,
    )


# ============================================================
# MAIN COLLECTOR
# ============================================================

def get_gold_18k():

    try:

        print(
            "📡 TGJU: requesting gold price...",
            flush=True,
        )

        response = fetch_tgju_page()

        print(
            f"🌐 TGJU HTTP: {response.status_code}",
            flush=True,
        )

        html = response.text

        # ----------------------------------------------------
        # Current price
        # ----------------------------------------------------

        price = extract_current_price(
            html
        )

        # ----------------------------------------------------
        # Extract intraday series
        # ----------------------------------------------------

        series = extract_price_series(
            html
        )

        print_series_diagnostic(
            series
        )

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        print(
            f"🟢 TGJU: "
            f"{price:,.0f} تومان",
            flush=True,
        )

        return {
            "symbol": "gold_18k",
            "price": price,
            "currency": "IRR",
            "timestamp": timestamp,
            "source": "tgju",
            "series": series,
        }

    except requests.RequestException as error:

        print(
            "🔴 TGJU REQUEST ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        raise

    except Exception as error:

        print(
            "🔴 TGJU ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        raise
