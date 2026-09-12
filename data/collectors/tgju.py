import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

TGJU_URL = "https://www.tgju.org/profile/geram18"

REQUEST_TIMEOUT = 15

MAX_SCRIPT_FILES = 10

MAX_CONTEXT_PER_MATCH = 1200

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
# HELPERS
# ============================================================

def clean_text(text):
    """
    حذف فاصله‌ها و نویزهای اضافی برای لاگ.
    """

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def get_context(
    text,
    position,
    radius=MAX_CONTEXT_PER_MATCH,
):
    """
    بخشی از متن اطراف یک match را برمی‌گرداند.
    """

    start = max(
        0,
        position - radius,
    )

    end = min(
        len(text),
        position + radius,
    )

    return clean_text(
        text[start:end]
    )


# ============================================================
# FIND SCRIPT FILES
# ============================================================

def find_script_urls(html):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    script_urls = []

    for script in soup.find_all(
        "script"
    ):

        src = script.get(
            "src"
        )

        if not src:
            continue

        url = urljoin(
            TGJU_URL,
            src,
        )

        parsed = urlparse(
            url
        )

        # فقط فایل‌های JS مربوط به خود TGJU
        if parsed.netloc not in (
            "www.tgju.org",
            "tgju.org",
        ):
            continue

        if url not in script_urls:

            script_urls.append(
                url
            )

    return script_urls[:MAX_SCRIPT_FILES]


# ============================================================
# SEARCH JAVASCRIPT
# ============================================================

def inspect_javascript(
    js_text,
    source_name,
):
    """
    جستجوی هدفمند برای پیدا کردن منبع داده نمودار.
    """

    print(
        "",
        flush=True,
    )

    print(
        f"🧩 JS SCAN: {source_name}",
        flush=True,
    )

    # --------------------------------------------------------
    # الگوهای مهم
    # --------------------------------------------------------

    patterns = [
        (
            "AJAX",
            r"\$\.ajax\s*\(",
        ),
        (
            "GET",
            r"\$\.get\s*\(",
        ),
        (
            "POST",
            r"\$\.post\s*\(",
        ),
        (
            "FETCH",
            r"\bfetch\s*\(",
        ),
        (
            "XHR",
            r"XMLHttpRequest",
        ),
        (
            "SERIES",
            r"\bseries\s*[:=]",
        ),
        (
            "CHART",
            r"profile_charts|technical_charts|chart",
        ),
        (
            "HISTORY",
            r"profile_history|historical|history",
        ),
        (
            "OHLC",
            r"\bohlc\b|open\s*[:=].*high\s*[:=].*low\s*[:=].*close",
        ),
        (
            "API",
            r"[/\"']api[/\"']|/api/|api/",
        ),
    ]

    found_any = False

    for label, pattern in patterns:

        match = re.search(
            pattern,
            js_text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        found_any = True

        context = get_context(
            js_text,
            match.start(),
        )

        print(
            f"   🔎 {label}:",
            flush=True,
        )

        print(
            f"      {context[:MAX_CONTEXT_PER_MATCH]}",
            flush=True,
        )

    if not found_any:

        print(
            "   — no relevant chart/API pattern",
            flush=True,
        )


# ============================================================
# EXTRACT POSSIBLE ENDPOINTS
# ============================================================

def find_candidate_endpoints(
    text
):
    """
    URLهای احتمالی مربوط به API / chart / history
    """

    candidates = set()

    # Absolute URLs
    absolute_urls = re.findall(
        r'https?://[^"\'\s<>]+',
        text,
        flags=re.IGNORECASE,
    )

    for url in absolute_urls:

        url_clean = url.rstrip(
            ".,);"
        )

        low = url_clean.lower()

        if any(
            key in low
            for key in (
                "/api/",
                "api.",
                "chart",
                "history",
                "historical",
                "ohlc",
                "series",
            )
        ):

            candidates.add(
                url_clean
            )

    # Relative paths
    relative_paths = re.findall(
        r'["\'](/[^"\']{1,250})["\']',
        text,
        flags=re.IGNORECASE,
    )

    for path in relative_paths:

        low = path.lower()

        if any(
            key in low
            for key in (
                "/api/",
                "chart",
                "history",
                "historical",
                "ohlc",
                "series",
            )
        ):

            candidates.add(
                path
            )

    return sorted(
        candidates
    )


# ============================================================
# TARGETED PAGE DISCOVERY
# ============================================================

def inspect_tgju_data(
    html
):

    print(
        "",
        flush=True,
    )

    print(
        "🔎 TGJU TARGETED CHART DISCOVERY",
        flush=True,
    )

    print(
        "-" * 60,
        flush=True,
    )

    html_lower = html.lower()

    # --------------------------------------------------------
    # 1. Important keywords
    # --------------------------------------------------------

    keywords = [
        "profile_charts",
        "technical_charts",
        "profile_history",
        "series",
        "ohlc",
        "$.ajax",
        "fetch(",
        "xmlhttprequest",
    ]

    print(
        "📊 IMPORTANT PAGE SIGNALS:",
        flush=True,
    )

    for keyword in keywords:

        count = html_lower.count(
            keyword.lower()
        )

        if count:

            print(
                f"   {keyword:<22}: {count}",
                flush=True,
            )

    # --------------------------------------------------------
    # 2. Inspect inline scripts
    # --------------------------------------------------------

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    inline_scripts = []

    for script in soup.find_all(
        "script"
    ):

        if script.get("src"):
            continue

        content = script.string

        if not content:
            content = script.get_text()

        if not content:
            continue

        inline_scripts.append(
            content
        )

    print(
        "",
        flush=True,
    )

    print(
        f"📜 INLINE JS BLOCKS: {len(inline_scripts)}",
        flush=True,
    )

    # فقط اسکریپت‌هایی که واقعاً نشانه دارند
    relevant_inline = 0

    for index, script in enumerate(
        inline_scripts
    ):

        low = script.lower()

        if not any(
            keyword in low
            for keyword in (
                "profile_charts",
                "technical_charts",
                "profile_history",
                "series",
                "ohlc",
                "$.ajax",
                "fetch(",
                "xmlhttprequest",
            )
        ):

            continue

        relevant_inline += 1

        inspect_javascript(
            script,
            f"inline-script-{index}",
        )

        if relevant_inline >= 5:
            break

    # --------------------------------------------------------
    # 3. Candidate endpoints directly in HTML
    # --------------------------------------------------------

    candidates = find_candidate_endpoints(
        html
    )

    print(
        "",
        flush=True,
    )

    if candidates:

        print(
            "🔗 CANDIDATE ENDPOINTS IN HTML:",
            flush=True,
        )

        for candidate in candidates[:20]:

            print(
                f"   {candidate}",
                flush=True,
            )

    else:

        print(
            "⚠️ No direct endpoint found in HTML.",
            flush=True,
        )

    # --------------------------------------------------------
    # 4. Find JavaScript files
    # --------------------------------------------------------

    script_urls = find_script_urls(
        html
    )

    print(
        "",
        flush=True,
    )

    print(
        f"📦 TGJU JS FILES FOUND: {len(script_urls)}",
        flush=True,
    )

    for index, url in enumerate(
        script_urls,
        start=1,
    ):

        print(
            f"   {index}. {url}",
            flush=True,
        )

    # --------------------------------------------------------
    # 5. Download only relevant JS files
    # --------------------------------------------------------

    print(
        "",
        flush=True,
    )

    print(
        "🧠 SCANNING TGJU JAVASCRIPT...",
        flush=True,
    )

    scanned = 0

    for url in script_urls:

        try:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=10,
            )

            if response.status_code != 200:
                continue

            js_text = response.text

            low = js_text.lower()

            # فقط فایل‌هایی که نشانه‌ای از chart/history/API دارند
            if not any(
                keyword in low
                for keyword in (
                    "profile_charts",
                    "technical_charts",
                    "profile_history",
                    "series",
                    "ohlc",
                    "$.ajax",
                    "fetch(",
                    "xmlhttprequest",
                    "/api/",
                )
            ):
                continue

            scanned += 1

            inspect_javascript(
                js_text,
                url,
            )

            js_candidates = find_candidate_endpoints(
                js_text
            )

            if js_candidates:

                print(
                    "   🔗 ENDPOINT CANDIDATES:",
                    flush=True,
                )

                for candidate in js_candidates[:15]:

                    print(
                        f"      {candidate}",
                        flush=True,
                    )

            if scanned >= 5:
                break

        except Exception as error:

            print(
                f"   ⚠️ JS scan failed: "
                f"{type(error).__name__}",
                flush=True,
            )

    # --------------------------------------------------------
    # 6. Direct OHLC check
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
            "🕯️ OHLC-LIKE STRUCTURE: FOUND",
            flush=True,
        )

    else:

        print(
            "❌ Direct OHLC data is NOT embedded in page HTML.",
            flush=True,
        )

    print(
        "",
        flush=True,
    )

    print(
        "🏁 TGJU DISCOVERY FINISHED",
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
        # Targeted discovery
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
