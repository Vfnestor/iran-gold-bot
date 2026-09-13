import json
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

TGJU_LIVE_URL = "https://call5.tgju.org/ajax.json"

REQUEST_TIMEOUT = 15

# فقط چند endpoint مهم را بررسی می‌کنیم
MAX_ENDPOINTS_TO_PROBE = 25

# حداکثر اسکریپت خارجی برای بررسی
MAX_EXTERNAL_SCRIPTS = 20

# داده‌ای که بیشتر از این فاصله داشته باشد intraday نیست
MAX_INTRADAY_GAP_SECONDS = 15 * 60

# حداقل تعداد نقطه برای ذخیره
MIN_INTRADAY_POINTS = 2

# پنجره قابل قبول برای داده intraday
INTRADAY_SAVE_WINDOW_HOURS = 6


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
    "Referer": TGJU_URL,
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
# URL HELPERS
# ============================================================

def _normalize_url(
    url,
    base_url=TGJU_URL,
):

    if not url:
        return None

    url = str(url).strip()

    url = url.strip(
        "\"'` "
    )

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

    url = url.replace(
        "\\/",
        "/",
    )

    url = url.replace(
        "\\u002F",
        "/",
    )

    url = url.replace(
        "\\u002f",
        "/",
    )

    url = url.replace(
        "&amp;",
        "&",
    )

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


# ============================================================
# CURRENT PRICE FROM HTML
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
        "Could not find 18K gold price on TGJU."
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
                "Referer": TGJU_URL,
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
                "⚠️ CALL5: geram18 price field not found.",
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
# GENERIC PRICE / TIMESTAMP PARSER
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


def _looks_like_timestamp(
    value,
):

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


def _extract_points_from_json(
    data,
):

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
                minutes=5
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

    def walk(
        obj,
    ):

        if isinstance(
            obj,
            dict,
        ):

            # --------------------------------------------
            # Common object forms
            # --------------------------------------------

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

                if key in obj:

                    timestamp_value = obj.get(
                        key
                    )

                    if _looks_like_timestamp(
                        timestamp_value
                    ):
                        break

            for key in price_keys:

                if key in obj:

                    candidate = obj.get(
                        key
                    )

                    if _normalize_price(
                        candidate
                    ) is not None:

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

            # --------------------------------------------
            # Array format:
            # [timestamp, price]
            # --------------------------------------------

            if len(obj) >= 2:

                first = obj[0]
                second = obj[1]

                if (
                    _looks_like_timestamp(first)
                    and _normalize_price(second)
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

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    unique = {}

    for point in points:

        unique[
            point["timestamp_ms"]
        ] = point

    result = list(
        unique.values()
    )

    result.sort(
        key=lambda x: x[
            "timestamp_ms"
        ]
    )

    return result


# ============================================================
# URL EXTRACTION FROM JAVASCRIPT
# ============================================================

def _extract_urls_from_text(
    text,
    base_url=TGJU_URL,
):

    urls = set()

    if not text:
        return urls

    patterns = [
        r"https?://[^\s\"'`<>\\]+",
        r"https?:\\/\\/[^\\s\"'`<>]+",
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:

            url = _normalize_url(
                match,
                base_url,
            )

            if url:
                urls.add(url)

    # --------------------------------------------------------
    # Relative strings
    # --------------------------------------------------------

    relative_pattern = (
        r"""["'`]([^"'`]{1,500})["'`]"""
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

        url = _normalize_url(
            candidate,
            base_url,
        )

        if url:
            urls.add(url)

    return urls


# ============================================================
# JS ENDPOINT EXTRACTION
# ============================================================

def _extract_endpoint_candidates(
    text,
):

    candidates = set()

    if not text:
        return candidates

    candidates.update(
        _extract_urls_from_text(
            text
        )
    )

    patterns = [

        # fetch(...)
        r"""fetch\s*\(\s*["'`]([^"'`]+)["'`]""",

        # $.ajax({ url: ... })
        (
            r"""\$\.ajax\s*\(\s*\{[\s\S]{0,3000}?"""
            r"""url\s*:\s*["'`]([^"'`]+)["'`]"""
        ),

        # $.get / $.getJSON / $.post
        (
            r"""\$\.(?:get|getJSON|post)\s*"""
            r"""\(\s*["'`]([^"'`]+)["'`]"""
        ),

        # axios
        (
            r"""axios\.(?:get|post|put|patch|delete)"""
            r"""\s*\(\s*["'`]([^"'`]+)["'`]"""
        ),

        # generic url
        r"""\burl\s*:\s*["'`]([^"'`]+)["'`]""",

        r"""\bendpoint\s*:\s*["'`]([^"'`]+)["'`]""",

        r"""\bdataUrl\s*:\s*["'`]([^"'`]+)["'`]""",

        r"""\bajaxUrl\s*:\s*["'`]([^"'`]+)["'`]""",

        r"""\bapiUrl\s*:\s*["'`]([^"'`]+)["'`]""",
    ]

    for pattern in patterns:

        try:

            matches = re.findall(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

        except Exception:
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

                url = _normalize_url(
                    value
                )

                if url:
                    candidates.add(
                        url
                    )

    return candidates


# ============================================================
# PRIORITY SCORING
# ============================================================

def _endpoint_score(
    url,
):

    lowered = url.lower()

    score = 0

    # مهم‌ترین کلمات
    if "geram18" in lowered:
        score += 100

    if "chart" in lowered:
        score += 50

    if "history" in lowered:
        score += 45

    if "historical" in lowered:
        score += 45

    if "ohlc" in lowered:
        score += 45

    if "candle" in lowered:
        score += 45

    if "series" in lowered:
        score += 40

    if "price" in lowered:
        score += 25

    if "market" in lowered:
        score += 20

    if "data" in lowered:
        score += 15

    if "ajax" in lowered:
        score += 15

    if "api" in lowered:
        score += 10

    # endpointهای unrelated مثل search را پایین می‌آوریم
    if "newsearch" in lowered:
        score -= 100

    if "search" in lowered:
        score -= 30

    return score


# ============================================================
# EXTRACT HISTORICAL SERIES FROM HTML
# ============================================================

def extract_price_series(
    html,
):

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
                        minutes=5
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
                key=lambda x: x[
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
            "❌ TGJU: no chartData series found.",
            flush=True,
        )

        return []

    candidate_series.sort(
        key=lambda candidate: (
            candidate["points"][-1]["timestamp_ms"],
            len(candidate["points"]),
        ),
        reverse=True,
    )

    best = candidate_series[0][
        "points"
    ]

    print(
        "",
        flush=True,
    )

    print(
        "🔎 TGJU CHART CANDIDATES:",
        len(candidate_series),
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

    return best


# ============================================================
# PROBE ENDPOINT
# ============================================================

def _probe_endpoint(
    url,
):

    try:

        print(
            "",
            flush=True,
        )

        print(
            f"🔎 PROBE: {url}",
            flush=True,
        )

        response = requests.get(
            url,
            headers={
                **HEADERS,
                "Referer": TGJU_URL,
                "Accept": (
                    "application/json,"
                    "text/plain,*/*"
                ),
            },
            timeout=REQUEST_TIMEOUT,
        )

        print(
            f"   HTTP={response.status_code} "
            f"| size={len(response.content):,}",
            flush=True,
        )

        if not response.ok:
            return []

        content_type = (
            response.headers.get(
                "content-type",
                "",
            ).lower()
        )

        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        data = None

        if (
            "json" in content_type
            or response.text.lstrip().startswith(
                ("{", "[")
            )
        ):

            try:
                data = response.json()

            except Exception:
                data = None

        if data is not None:

            points = _extract_points_from_json(
                data
            )

            print(
                f"   📊 JSON POINTS: "
                f"{len(points)}",
                flush=True,
            )

            if points:

                print(
                    f"   FIRST: "
                    f"{points[0]['timestamp'].isoformat()} "
                    f"| {points[0]['price']:,.0f}",
                    flush=True,
                )

                print(
                    f"   LAST : "
                    f"{points[-1]['timestamp'].isoformat()} "
                    f"| {points[-1]['price']:,.0f}",
                    flush=True,
                )

            return points

        # ----------------------------------------------------
        # Maybe HTML / JS containing chartData
        # ----------------------------------------------------

        if "chartData" in response.text:

            points = extract_price_series(
                response.text
            )

            if points:
                return points

        return []

    except Exception as error:

        print(
            f"   ⚠️ PROBE ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return []


# ============================================================
# DISCOVER + TEST ENDPOINTS
# ============================================================

def discover_intraday_endpoints(
    html,
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
        "🔬 TGJU LIVE / CHART ENDPOINT DISCOVERY",
        flush=True,
    )

    print(
        "=" * 80,
        flush=True,
    )

    candidates = set()

    # --------------------------------------------------------
    # Known live endpoint
    # --------------------------------------------------------

    candidates.add(
        TGJU_LIVE_URL
    )

    # --------------------------------------------------------
    # URLs inside HTML
    # --------------------------------------------------------

    candidates.update(
        _extract_urls_from_text(
            html
        )
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    # --------------------------------------------------------
    # Inline scripts
    # --------------------------------------------------------

    for script in soup.find_all(
        "script"
    ):

        if script.get("src"):
            continue

        text = script.string

        if not text:
            text = script.get_text()

        if not text:
            continue

        candidates.update(
            _extract_endpoint_candidates(
                text
            )
        )

    # --------------------------------------------------------
    # External scripts
    # --------------------------------------------------------

    script_urls = []

    for script in soup.find_all(
        "script"
    ):

        src = script.get(
            "src"
        )

        if not src:
            continue

        url = _normalize_url(
            src,
            TGJU_URL,
        )

        if url and url not in script_urls:
            script_urls.append(
                url
            )

    for script_url in script_urls[
        :MAX_EXTERNAL_SCRIPTS
    ]:

        try:

            response = requests.get(
                script_url,
                headers={
                    **HEADERS,
                    "Referer": TGJU_URL,
                },
                timeout=REQUEST_TIMEOUT,
            )

            if not response.ok:
                continue

            js_text = response.text

            # فقط JSهایی که احتمال ارتباط با chart دارند
            lowered = js_text.lower()

            interesting = any(
                key in lowered
                for key in (
                    "chartdata",
                    "reload_charts",
                    "highcharts",
                    "candlestick",
                    "ohlc",
                    "geram18",
                    "chart",
                )
            )

            if not interesting:
                continue

            candidates.update(
                _extract_endpoint_candidates(
                    js_text
                )
            )

        except Exception:
            continue

    # --------------------------------------------------------
    # Remove obviously unrelated endpoints
    # --------------------------------------------------------

    filtered = []

    for url in candidates:

        lowered = url.lower()

        if (
            "newsearch" in lowered
            and "geram18" not in lowered
        ):
            continue

        if (
            "search" in lowered
            and "chart" not in lowered
            and "geram18" not in lowered
        ):
            continue

        if _looks_like_endpoint(
            url
        ):
            filtered.append(
                url
            )

    filtered = sorted(
        set(filtered),
        key=lambda item: (
            -_endpoint_score(item),
            item,
        ),
    )

    print(
        f"🎯 PRIORITIZED ENDPOINTS: "
        f"{len(filtered)}",
        flush=True,
    )

    # --------------------------------------------------------
    # Probe only best candidates
    # --------------------------------------------------------

    all_points = []

    for url in filtered[
        :MAX_ENDPOINTS_TO_PROBE
    ]:

        points = _probe_endpoint(
            url
        )

        if points:
            all_points.extend(
                points
            )

            # اگر یک endpoint واقعاً intraday داد
            # فعلاً endpointهای ضعیف‌تر را هم می‌توانیم
            # بررسی کنیم، اما این سری را نگه می‌داریم.

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    unique = {}

    for point in all_points:

        unique[
            point["timestamp_ms"]
        ] = point

    result = list(
        unique.values()
    )

    result.sort(
        key=lambda x: x[
            "timestamp_ms"
        ]
    )

    print(
        "",
        flush=True,
    )

    print(
        f"📊 DISCOVERY TOTAL POINTS: "
        f"{len(result)}",
        flush=True,
    )

    print(
        "=" * 80,
        flush=True,
    )

    return result


# ============================================================
# SELECT REAL INTRADAY DATA
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
            <= now + timedelta(
                minutes=2
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
            f"   source points: {len(series)}",
            flush=True,
        )

        print(
            f"   recent points: {len(recent)}",
            flush=True,
        )

        print(
            "   ❌ Not enough recent intraday points.",
            flush=True,
        )

        return []

    recent.sort(
        key=lambda x: x[
            "timestamp_ms"
        ]
    )

    # --------------------------------------------------------
    # Build continuous segments
    # --------------------------------------------------------

    segments = []

    current = [
        recent[0]
    ]

    for previous, point in zip(
        recent[:-1],
        recent[1:],
    ):

        delta = (
            point["timestamp_ms"]
            - previous["timestamp_ms"]
        ) / 1000

        if (
            delta > 0
            and delta <= MAX_INTRADAY_GAP_SECONDS
        ):

            current.append(
                point
            )

        else:

            if len(current) >= MIN_INTRADAY_POINTS:
                segments.append(
                    current
                )

            current = [
                point
            ]

    if len(current) >= MIN_INTRADAY_POINTS:
        segments.append(
            current
        )

    if not segments:

        print(
            "⚠️ TGJU: recent points are not "
            "a continuous intraday series.",
            flush=True,
        )

        return []

    selected = max(
        segments,
        key=lambda segment: segment[-1][
            "timestamp_ms"
        ],
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

    for previous, point in zip(
        selected[:-1],
        selected[1:],
    ):

        delta = (
            point["timestamp_ms"]
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
# SAVE
# ============================================================

def save_intraday_series(
    series,
):

    if not series:

        print(
            "⚠️ TGJU: no intraday data to save.",
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
            "🛑 TGJU: data blocked. "
            "No valid intraday series.",
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
# MAIN
# ============================================================

def get_gold_18k():

    try:

        print(
            "📡 TGJU: requesting gold price...",
            flush=True,
        )

        response = fetch_tgju_page()

        print(
            f"🌐 TGJU HTTP: "
            f"{response.status_code}",
            flush=True,
        )

        html = response.text

        # ====================================================
        # 1. PRICE FROM HTML
        # ====================================================

        html_price = extract_current_price(
            html
        )

        # ====================================================
        # 2. LIVE CALL5
        # ====================================================

        live_point = fetch_live_call5()

        if live_point:

            price = int(
                live_point["price"]
            )

        else:

            price = html_price

        # ====================================================
        # 3. EXISTING HTML CHART
        # ====================================================

        historical_series = extract_price_series(
            html
        )

        # ====================================================
        # 4. FIND REAL LIVE/CHART ENDPOINT
        # ====================================================

        discovered_series = (
            discover_intraday_endpoints(
                html
            )
        )

        # ====================================================
        # 5. COMBINE
        # ====================================================

        combined = []

        combined.extend(
            discovered_series
        )

        # live point is useful as the newest point,
        # but alone it must NEVER create candles.
        if live_point:

            combined.append(
                live_point
            )

        # Historical chart is included only for diagnostics.
        # It will be filtered out before storage if daily.
        combined.extend(
            historical_series
        )

        unique = {}

        for point in combined:

            unique[
                point["timestamp_ms"]
            ] = point

        combined = list(
            unique.values()
        )

        combined.sort(
            key=lambda x: x[
                "timestamp_ms"
            ]
        )

        # ====================================================
        # 6. DIAGNOSTIC
        # ====================================================

        print(
            "",
            flush=True,
        )

        print(
            "🕯️ TGJU FINAL SERIES:",
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
        # 7. SAVE ONLY REAL INTRADAY
        # ====================================================

        save_intraday_series(
            combined
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
