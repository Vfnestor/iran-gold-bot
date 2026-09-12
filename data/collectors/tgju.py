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
# SAFE REQUEST
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
# TGJU DATA / CHART DISCOVERY
# ============================================================

def inspect_tgju_data(html):

    print(
        "",
        flush=True,
    )

    print(
        "🔎 TGJU HISTORICAL / CHART TEST",
        flush=True,
    )

    print(
        "-" * 50,
        flush=True,
    )

    html_lower = html.lower()

    # --------------------------------------------------------
    # Keyword scan
    # --------------------------------------------------------

    keywords = [
        "open",
        "high",
        "low",
        "close",
        "ohlc",
        "historical",
        "history",
        "chart",
        "series",
    ]

    print(
        "📊 TGJU PAGE KEYWORDS:",
        flush=True,
    )

    for keyword in keywords:

        count = html_lower.count(
            keyword
        )

        if count > 0:

            print(
                f"   {keyword:<12}: {count}",
                flush=True,
            )

    # --------------------------------------------------------
    # Search possible API URLs
    # --------------------------------------------------------

    urls = re.findall(
        r'https?://[^"\']+',
        html,
    )

    possible_urls = set()

    for url in urls:

        url_lower = url.lower()

        if any(
            keyword in url_lower
            for keyword in [
                "api",
                "chart",
                "history",
                "historical",
                "widget",
                "data",
            ]
        ):

            possible_urls.add(
                url
            )

    # --------------------------------------------------------
    # Search relative API paths
    # --------------------------------------------------------

    relative_paths = re.findall(
        r'["\']([^"\']*(?:api|chart|history|historical|widget|series|data)[^"\']*)["\']',
        html,
        flags=re.IGNORECASE,
    )

    for path in relative_paths:

        if len(path) < 300:

            possible_urls.add(
                path
            )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    if possible_urls:

        print(
            "",
            flush=True,
        )

        print(
            "🔗 POSSIBLE TGJU DATA ENDPOINTS:",
            flush=True,
        )

        counter = 0

        for url in sorted(
            possible_urls
        ):

            print(
                f"   {url[:500]}",
                flush=True,
            )

            counter += 1

            # جلوگیری از شلوغ شدن لاگ
            if counter >= 30:
                break

    else:

        print(
            "",
            flush=True,
        )

        print(
            "⚠️ No obvious API/chart endpoint found in page.",
            flush=True,
        )

    # --------------------------------------------------------
    # Look for OHLC-like structures
    # --------------------------------------------------------

    ohlc_patterns = [
        r'"open"\s*:',
        r'"high"\s*:',
        r'"low"\s*:',
        r'"close"\s*:',
        r"'open'\s*:",
        r"'high'\s*:",
        r"'low'\s*:",
        r"'close'\s*:",
    ]

    ohlc_found = []

    for pattern in ohlc_patterns:

        if re.search(
            pattern,
            html,
            flags=re.IGNORECASE,
        ):

            ohlc_found.append(
                pattern
            )

    print(
        "",
        flush=True,
    )

    if ohlc_found:

        print(
            "🕯️ POSSIBLE OHLC DATA: FOUND",
            flush=True,
        )

        print(
            "⚠️ This is only a discovery result.",
            flush=True,
        )

        print(
            "⚠️ It does NOT yet mean the data is usable.",
            flush=True,
        )

    else:

        print(
            "❌ Direct OHLC structure not found in page HTML.",
            flush=True,
        )

    print(
        "-" * 50,
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
        # Historical / chart discovery
        # ----------------------------------------------------

        inspect_tgju_data(
            html
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
