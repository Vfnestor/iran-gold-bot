import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from database import save_tgju_price_points


# ============================================================
# CONFIG
# ============================================================

TGJU_URL = "https://www.tgju.org/profile/geram18"

REQUEST_TIMEOUT = 15

MAX_EXTERNAL_SCRIPTS = 30
MAX_ENDPOINTS_TO_PRINT = 100

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
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.tgju.org/",
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
# DEBUG HELPERS
# ============================================================

def _normalize_url(url, base_url=TGJU_URL):

    if not url:
        return None

    url = url.strip()

    if not url:
        return None

    url = url.strip("\"'` ")

    if not url:
        return None

    if url.startswith(
        (
            "javascript:",
            "mailto:",
            "tel:",
            "data:",
        )
    ):
        return None

    full_url = urljoin(
        base_url,
        url,
    )

    parsed = urlparse(
        full_url
    )

    if parsed.scheme not in (
        "http",
        "https",
    ):
        return None

    return full_url.split(
        "#",
        1,
    )[0]


def _looks_like_endpoint(url):

    if not url:
        return False

    lowered = url.lower()

    keywords = (
        "api",
        "ajax",
        "chart",
        "graph",
        "json",
        "data",
        "history",
        "historical",
        "price",
        "prices",
        "quote",
        "quotes",
        "ticker",
        "market",
        "candl",
        "ohlc",
        "series",
        "profile",
        "getdata",
        "get_data",
        "fetch",
        "load",
        "update",
    )

    return any(
        keyword in lowered
        for keyword in keywords
    )


def _clean_js_url(raw_url):

    if not raw_url:
        return None

    raw_url = raw_url.strip()

    raw_url = raw_url.replace(
        "\\/",
        "/",
    )

    raw_url = raw_url.replace(
        "\\u002F",
        "/",
    )

    raw_url = raw_url.replace(
        "\\u002f",
        "/",
    )

    raw_url = raw_url.replace(
        "&amp;",
        "&",
    )

    return _normalize_url(
        raw_url,
        TGJU_URL,
    )


def _extract_urls_from_text(
    text,
    base_url=TGJU_URL,
):

    urls = set()

    if not text:
        return urls

    # --------------------------------------------------------
    # Absolute URLs
    # --------------------------------------------------------

    absolute_patterns = [
        r"https?://[^\s\"'`<>\\]+",
        r"https?:\\/\\/[^\\s\"'`<>]+",
    ]

    for pattern in absolute_patterns:

        for match in re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):

            url = _clean_js_url(
                match
            )

            if url:
                urls.add(url)

    # --------------------------------------------------------
    # Relative URLs
    # --------------------------------------------------------

    relative_pattern = (
        r"""["'`]"""
        r"""([^"'`]{1,500})"""
        r"""["'`]"""
    )

    for match in re.findall(
        relative_pattern,
        text,
    ):

        candidate = match.strip()

        if not candidate.startswith(
            (
                "/",
                "./",
                "../",
                "api/",
                "ajax/",
            )
        ):
            continue

        if not _looks_like_endpoint(
            candidate
        ):
            continue

        url = _clean_js_url(
            candidate
        )

        if url:
            urls.add(url)

    return urls


def _extract_endpoint_candidates(text):

    candidates = set()

    if not text:
        return candidates

    # --------------------------------------------------------
    # Direct URLs
    # --------------------------------------------------------

    candidates.update(
        _extract_urls_from_text(
            text
        )
    )

    # --------------------------------------------------------
    # fetch(...)
    # --------------------------------------------------------

    fetch_patterns = [
        r"""fetch\s*\(\s*["'`]([^"'`]+)["'`]""",
        r"""fetch\s*\(\s*`([^`]+)`""",
    ]

    # --------------------------------------------------------
    # $.ajax(...)
    # --------------------------------------------------------

    ajax_patterns = [
        (
            r"""\$\.ajax\s*\(\s*\{[\s\S]{0,3000}?"""
            r"""url\s*:\s*["'`]([^"'`]+)["'`]"""
        ),
        (
            r"""\bajax\s*\(\s*\{[\s\S]{0,3000}?"""
            r"""url\s*:\s*["'`]([^"'`]+)["'`]"""
        ),
    ]

    # --------------------------------------------------------
    # $.get / $.post
    # --------------------------------------------------------

    jquery_patterns = [
        r"""\$\.(?:get|getJSON|post)\s*\(\s*["'`]([^"'`]+)["'`]""",
        r"""\b(?:get|getJSON|post)\s*\(\s*["'`]([^"'`]+)["'`]""",
    ]

    # --------------------------------------------------------
    # axios
    # --------------------------------------------------------

    axios_patterns = [
        (
            r"""axios\.(?:get|post|put|patch|delete)"""
            r"""\s*\(\s*["'`]([^"'`]+)["'`]"""
        ),
        (
            r"""axios\s*\(\s*\{[\s\S]{0,3000}?"""
            r"""url\s*:\s*["'`]([^"'`]+)["'`]"""
        ),
    ]

    # --------------------------------------------------------
    # XMLHttpRequest
    # --------------------------------------------------------

    xhr_patterns = [
        (
            r"""\.open\s*\(\s*["'`]"""
            r"""(?:GET|POST|PUT|PATCH|DELETE)["'`]"""
            r"""\s*,\s*["'`]([^"'`]+)["'`]"""
        ),
        (
            r"""\.open\s*\(\s*["'`]([^"'`]+)["'`]"""
            r"""\s*,\s*["'`]([^"'`]+)["'`]"""
        ),
    ]

    # --------------------------------------------------------
    # Generic URL patterns
    # --------------------------------------------------------

    generic_patterns = [
        r"""\burl\s*:\s*["'`]([^"'`]+)["'`]""",
        r"""\bendpoint\s*:\s*["'`]([^"'`]+)["'`]""",
        r"""\bendpointUrl\s*:\s*["'`]([^"'`]+)["'`]""",
        r"""\bapiUrl\s*:\s*["'`]([^"'`]+)["'`]""",
        r"""\bapi_url\s*:\s*["'`]([^"'`]+)["'`]""",
        r"""\bdataUrl\s*:\s*["'`]([^"'`]+)["'`]""",
        r"""\bdata_url\s*:\s*["'`]([^"'`]+)["'`]""",
        r"""\bajaxUrl\s*:\s*["'`]([^"'`]+)["'`]""",
        r"""\bajax_url\s*:\s*["'`]([^"'`]+)["'`]""",
    ]

    all_patterns = (
        fetch_patterns
        + ajax_patterns
        + jquery_patterns
        + axios_patterns
        + xhr_patterns
        + generic_patterns
    )

    for pattern in all_patterns:

        try:

            matches = re.findall(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

        except re.error:

            continue

        for match in matches:

            if isinstance(
                match,
                tuple,
            ):
                values = match
            else:
                values = (
                    match,
                )

            for value in values:

                url = _clean_js_url(
                    value
                )

                if url:
                    candidates.add(url)

    return candidates


def _print_endpoint_context(
    text,
    endpoint,
    label="",
):

    if not text or not endpoint:
        return

    search_values = [
        endpoint,
        endpoint.replace(
            "/",
            "\\/",
        ),
    ]

    position = -1

    for value in search_values:

        position = text.find(
            value
        )

        if position >= 0:
            break

    if position < 0:
        return

    start = max(
        0,
        position - 180,
    )

    end = min(
        len(text),
        position + len(endpoint) + 300,
    )

    context = text[
        start:end
    ]

    context = re.sub(
        r"\s+",
        " ",
        context,
    )

    print(
        f"   {label}CONTEXT: "
        f"{context[:700]}",
        flush=True,
    )


# ============================================================
# TGJU ENDPOINT DEBUG
# ============================================================

def debug_tgju_endpoints(
    html,
    page_url=TGJU_URL,
):

    print(
        "",
        flush=True,
    )

    print(
        "=" * 80,
        flush=True,
    )

    print(
        "🔬 TGJU ENDPOINT DISCOVERY DEBUG",
        flush=True,
    )

    print(
        "=" * 80,
        flush=True,
    )

    print(
        f"PAGE: {page_url}",
        flush=True,
    )

    print(
        f"HTML SIZE: {len(html):,} chars",
        flush=True,
    )

    print(
        "-" * 80,
        flush=True,
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    # ========================================================
    # 1. URLs موجود در HTML
    # ========================================================

    html_urls = _extract_urls_from_text(
        html,
        page_url,
    )

    endpoint_urls = {
        url
        for url in html_urls
        if _looks_like_endpoint(url)
    }

    print(
        "",
        flush=True,
    )

    print(
        f"🌐 HTML URLS FOUND: "
        f"{len(html_urls)}",
        flush=True,
    )

    print(
        f"🎯 POSSIBLE ENDPOINT URLS: "
        f"{len(endpoint_urls)}",
        flush=True,
    )

    if endpoint_urls:

        print(
            "",
            flush=True,
        )

        print(
            "TGJU POSSIBLE ENDPOINTS FROM HTML:",
            flush=True,
        )

        for index, url in enumerate(
            sorted(endpoint_urls),
            start=1,
        ):

            if index > MAX_ENDPOINTS_TO_PRINT:

                print(
                    f"   ... more than "
                    f"{MAX_ENDPOINTS_TO_PRINT} endpoints",
                    flush=True,
                )

                break

            print(
                f"   [{index}] {url}",
                flush=True,
            )

    # ========================================================
    # 2. Inline JavaScript
    # ========================================================

    print(
        "",
        flush=True,
    )

    print(
        "-" * 80,
        flush=True,
    )

    print(
        "📜 INLINE JAVASCRIPT SCAN",
        flush=True,
    )

    print(
        "-" * 80,
        flush=True,
    )

    inline_scripts = []

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

        inline_scripts.append(
            (
                script_index,
                script_text,
            )
        )

    print(
        f"INLINE SCRIPTS: "
        f"{len(inline_scripts)}",
        flush=True,
    )

    inline_candidates = set()

    for script_index, script_text in inline_scripts:

        candidates = _extract_endpoint_candidates(
            script_text
        )

        interesting = {
            url
            for url in candidates
            if _looks_like_endpoint(url)
        }

        if not interesting:
            continue

        print(
            "",
            flush=True,
        )

        print(
            f"📌 INLINE SCRIPT #{script_index}",
            flush=True,
        )

        for url in sorted(
            interesting
        ):

            inline_candidates.add(
                url
            )

            print(
                f"   → {url}",
                flush=True,
            )

            _print_endpoint_context(
                script_text,
                url,
                label="   ",
            )

    # ========================================================
    # 3. External JavaScript
    # ========================================================

    print(
        "",
        flush=True,
    )

    print(
        "-" * 80,
        flush=True,
    )

    print(
        "📦 EXTERNAL JAVASCRIPT SCAN",
        flush=True,
    )

    print(
        "-" * 80,
        flush=True,
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

        full_url = _normalize_url(
            src,
            page_url,
        )

        if not full_url:
            continue

        if full_url not in script_urls:

            script_urls.append(
                full_url
            )

    print(
        f"EXTERNAL SCRIPTS FOUND: "
        f"{len(script_urls)}",
        flush=True,
    )

    external_candidates = set()

    scripts_checked = 0

    for script_url in script_urls:

        if (
            scripts_checked
            >= MAX_EXTERNAL_SCRIPTS
        ):

            print(
                f"⚠️ Reached "
                f"MAX_EXTERNAL_SCRIPTS="
                f"{MAX_EXTERNAL_SCRIPTS}",
                flush=True,
            )

            break

        scripts_checked += 1

        print(
            "",
            flush=True,
        )

        print(
            f"📥 JS #{scripts_checked}: "
            f"{script_url}",
            flush=True,
        )

        try:

            js_response = requests.get(
                script_url,
                headers={
                    **HEADERS,
                    "Referer": page_url,
                },
                timeout=REQUEST_TIMEOUT,
            )

            print(
                f"   HTTP: "
                f"{js_response.status_code} "
                f"| SIZE: "
                f"{len(js_response.text):,}",
                flush=True,
            )

            if not js_response.ok:
                continue

            js_text = js_response.text

            candidates = _extract_endpoint_candidates(
                js_text
            )

            interesting = {
                url
                for url in candidates
                if _looks_like_endpoint(url)
            }

            if not interesting:

                filename = (
                    urlparse(
                        script_url
                    )
                    .path
                    .lower()
                )

                if any(
                    keyword in filename
                    for keyword in (
                        "chart",
                        "graph",
                        "profile",
                        "market",
                        "price",
                        "data",
                        "api",
                    )
                ):

                    print(
                        "   ⚠️ Interesting JS filename "
                        "but no endpoint string found.",
                        flush=True,
                    )

                continue

            for url in sorted(
                interesting
            ):

                external_candidates.add(
                    url
                )

                print(
                    f"   🎯 ENDPOINT: "
                    f"{url}",
                    flush=True,
                )

                _print_endpoint_context(
                    js_text,
                    url,
                    label="      ",
                )

        except Exception as error:

            print(
                f"   ⚠️ JS FETCH ERROR: "
                f"{type(error).__name__}: "
                f"{error}",
                flush=True,
            )

    # ========================================================
    # 4. TGJU keyword scan
    # ========================================================

    print(
        "",
        flush=True,
    )

    print(
        "-" * 80,
        flush=True,
    )

    print(
        "🔎 TGJU CHART KEYWORD SCAN",
        flush=True,
    )

    print(
        "-" * 80,
        flush=True,
    )

    combined_text = html

    keyword_patterns = [
        "chartData",
        "msHighcharts",
        "Highcharts",
        "candlestick",
        "ohlc",
        "series",
        "ajax",
        "fetch(",
        "axios",
        "XMLHttpRequest",
        "getJSON",
        "api/",
        "/api/",
        "chart/",
        "/chart/",
        "graph/",
        "/graph/",
        "history",
        "historical",
        "price",
        "prices",
    ]

    for keyword in keyword_patterns:

        count = combined_text.lower().count(
            keyword.lower()
        )

        if count > 0:

            print(
                f"   {keyword:<22} "
                f"=> {count}",
                flush=True,
            )

    # ========================================================
    # 5. Final endpoint list
    # ========================================================

    all_candidates = (
        endpoint_urls
        | inline_candidates
        | external_candidates
    )

    print(
        "",
        flush=True,
    )

    print(
        "=" * 80,
        flush=True,
    )

    print(
        "🎯 TGJU API / AJAX / CHART ENDPOINTS",
        flush=True,
    )

    print(
        "=" * 80,
        flush=True,
    )

    if not all_candidates:

        print(
            "❌ NO POSSIBLE ENDPOINT FOUND.",
            flush=True,
        )

        print(
            "The endpoint may be constructed "
            "dynamically or loaded by another mechanism.",
            flush=True,
        )

    else:

        for index, url in enumerate(
            sorted(all_candidates),
            start=1,
        ):

            if index > MAX_ENDPOINTS_TO_PRINT:

                print(
                    f"... "
                    f"{len(all_candidates) - MAX_ENDPOINTS_TO_PRINT} "
                    f"more endpoints hidden.",
                    flush=True,
                )

                break

            print(
                f"[{index}] {url}",
                flush=True,
            )

    print(
        "=" * 80,
        flush=True,
    )

    print(
        "🔬 ENDPOINT DISCOVERY FINISHED",
        flush=True,
    )

    print(
        "=" * 80,
        flush=True,
    )

    print(
        "",
        flush=True,
    )

    return sorted(
        all_candidates
    )


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
        match.group(1).replace(
            ",",
            "",
        )
    )

    if price <= 0:

        raise RuntimeError(
            "Invalid TGJU gold price."
        )

    return price


# ============================================================
# TIMESTAMP HELPER
# ============================================================

def _timestamp_from_ms(
    timestamp_ms,
):

    try:

        return datetime.fromtimestamp(
            int(timestamp_ms) / 1000,
            tz=timezone.utc,
        )

    except Exception:

        return None


# ============================================================
# FIND TGJU PRICE SERIES
# ============================================================

def extract_price_series(html):

    """
    استخراج سری‌های قیمت از chartDataهای TGJU.

    این قسمت فعلاً همان parser قبلی است.
    هدف این مرحله فقط پیدا کردن endpoint واقعی است.
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

        if "msHighcharts" not in script_text:
            continue

        chart_positions = [
            match.start()
            for match in re.finditer(
                r"chartData\s*:",
                script_text,
                flags=re.IGNORECASE,
            )
        ]

        for chart_index, position in enumerate(
            chart_positions
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

                try:

                    timestamp_ms = int(
                        timestamp_raw
                    )

                    price = float(
                        price_raw
                    )

                except ValueError:

                    continue

                if timestamp_ms <= 0:
                    continue

                if price <= 0:
                    continue

                timestamp = _timestamp_from_ms(
                    timestamp_ms
                )

                if timestamp is None:
                    continue

                if timestamp > (
                    now + timedelta(
                        minutes=5
                    )
                ):
                    continue

                points.append(
                    {
                        "timestamp": timestamp,
                        "timestamp_ms": timestamp_ms,
                        "price": price,
                    }
                )

            if len(points) < 5:
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
                key=lambda x: x[
                    "timestamp_ms"
                ]
            )

            if len(cleaned) < 5:
                continue

            first_timestamp = cleaned[0][
                "timestamp"
            ]

            last_timestamp = cleaned[-1][
                "timestamp"
            ]

            candidate_series.append(
                {
                    "script_index": script_index,
                    "chart_index": chart_index,
                    "points": cleaned,
                    "count": len(cleaned),
                    "first": first_timestamp,
                    "last": last_timestamp,
                }
            )

    if not candidate_series:

        print(
            "❌ TGJU: no chart candidates found.",
            flush=True,
        )

        return []

    print(
        "",
        flush=True,
    )

    print(
        "🔎 TGJU CHART CANDIDATES:",
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

        print(
            f"   #{index} "
            f"| points={candidate['count']} "
            f"| first={candidate['first'].isoformat()} "
            f"| last={candidate['last'].isoformat()}",
            flush=True,
        )

    print(
        "-" * 70,
        flush=True,
    )

    candidate_series.sort(
        key=lambda candidate: (
            candidate["last"],
            candidate["count"],
        ),
        reverse=True,
    )

    best_candidate = candidate_series[0]

    result = best_candidate[
        "points"
    ]

    print(
        "✅ TGJU SELECTED SERIES:",
        flush=True,
    )

    print(
        f"   points={len(result)}",
        flush=True,
    )

    print(
        f"   first={result[0]['timestamp'].isoformat()}",
        flush=True,
    )

    print(
        f"   last={result[-1]['timestamp'].isoformat()}",
        flush=True,
    )

    print(
        "-" * 70,
        flush=True,
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
# SAVE RAW TGJU SERIES
# ============================================================

def save_intraday_series(series):

    if not series:

        print(
            "⚠️ TGJU: no intraday points to save.",
            flush=True,
        )

        return {
            "received": 0,
            "saved": 0,
            "duplicates": 0,
        }

    result = save_tgju_price_points(
        series,
        symbol="gold_18k",
    )

    print(
        "💾 TGJU RAW SERIES: "
        f"received={result['received']} "
        f"saved={result['saved']} "
        f"duplicates={result['duplicates']}",
        flush=True,
    )

    return result


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

        # ====================================================
        # NEW DEBUG STEP
        # ====================================================
        #
        # فقط endpointها را پیدا می‌کند.
        # هیچ endpoint جدیدی برای دریافت قیمت اجرا نمی‌شود.
        #

        debug_tgju_endpoints(
            html,
            TGJU_URL,
        )

        # ====================================================
        # CURRENT PRICE
        # ====================================================

        price = extract_current_price(
            html
        )

        # ====================================================
        # INTRADAY SERIES
        # ====================================================

        series = extract_price_series(
            html
        )

        print_series_diagnostic(
            series
        )

        # ====================================================
        # SAVE RAW SERIES
        # ====================================================

        save_intraday_series(
            series
        )

        # ====================================================
        # TIMESTAMP
        # ====================================================

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
