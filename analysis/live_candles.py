from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from data.collectors.tgju import (
    fetch_tgju_page,
    extract_price_series,
)


# ============================================================
# CONFIG
# ============================================================

WINDOW_MINUTES = 60

TIMEFRAMES = {
    "5m": 5,
    "15m": 15,
    "1h": 60,
}

# TGJU returns Rial.
# The analysis system works in Toman.
RIAL_TO_TOMAN = 10.0


# ============================================================
# SAFE HELPERS
# ============================================================

def _to_float(
    value: Any,
) -> Optional[float]:
    """
    تبدیل امن مقدار به float.
    """

    try:
        if value is None:
            return None

        if isinstance(value, str):
            value = (
                value
                .replace(",", "")
                .replace("٬", "")
                .replace(" ", "")
            )

        number = float(value)

        if number <= 0:
            return None

        return number

    except (
        TypeError,
        ValueError,
    ):
        return None


def _normalize_timestamp(
    value: Any,
) -> Optional[datetime]:
    """
    نرمال‌سازی timestamp.

    پشتیبانی از:
    - datetime
    - Unix seconds
    - Unix milliseconds
    - ISO datetime
    """

    if isinstance(
        value,
        datetime,
    ):
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        )

    if isinstance(
        value,
        (int, float),
    ):
        try:
            number = float(value)

            # Unix milliseconds
            if number > 10_000_000_000:
                number /= 1000.0

            return datetime.fromtimestamp(
                number,
                tz=timezone.utc,
            )

        except Exception:
            return None

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # --------------------------------------------------------
    # ISO datetime
    # --------------------------------------------------------

    try:
        parsed = datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # Numeric timestamp stored as string
    # --------------------------------------------------------

    try:
        number = float(text)

        if number > 10_000_000_000:
            number /= 1000.0

        return datetime.fromtimestamp(
            number,
            tz=timezone.utc,
        )

    except Exception:
        return None


# ============================================================
# RAW POINT NORMALIZATION
# ============================================================

def _normalize_points(
    series: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    تبدیل داده خام TGJU به نقاط استاندارد.

    خروجی هر نقطه:

    {
        timestamp,
        timestamp_ms,
        price
    }
    """

    points: List[
        Dict[str, Any]
    ] = []

    rejected_timestamp = 0
    rejected_price = 0

    for item in series:

        if not isinstance(
            item,
            dict,
        ):
            continue

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        raw_timestamp = (
            item.get("timestamp")
            or item.get("time")
            or item.get("datetime")
            or item.get("date")
            or item.get("created_at")
        )

        timestamp = _normalize_timestamp(
            raw_timestamp
        )

        if timestamp is None:
            rejected_timestamp += 1
            continue

        # ----------------------------------------------------
        # Price
        # ----------------------------------------------------

        raw_price = (
            item.get("price")
            or item.get("value")
            or item.get("close")
            or item.get("last")
        )

        price = _to_float(
            raw_price
        )

        if price is None:
            rejected_price += 1
            continue

        # ----------------------------------------------------
        # TGJU price is Rial.
        # Convert immediately to Toman.
        # ----------------------------------------------------

        price_toman = (
            price / RIAL_TO_TOMAN
        )

        points.append(
            {
                "timestamp": timestamp,
                "timestamp_ms": int(
                    timestamp.timestamp()
                    * 1000
                ),
                "price": price_toman,
            }
        )

    # --------------------------------------------------------
    # Sort chronologically
    # --------------------------------------------------------

    points.sort(
        key=lambda item: item[
            "timestamp"
        ]
    )

    # --------------------------------------------------------
    # Remove duplicate timestamps.
    #
    # If multiple values have the same timestamp,
    # keep the latest one.
    # --------------------------------------------------------

    unique: Dict[
        int,
        Dict[str, Any],
    ] = {}

    for point in points:

        unique[
            point["timestamp_ms"]
        ] = point

    normalized = list(
        unique.values()
    )

    normalized.sort(
        key=lambda item: item[
            "timestamp"
        ]
    )

    # --------------------------------------------------------
    # Diagnostic
    # --------------------------------------------------------

    print(
        "📊 TGJU RAW SERIES:",
        len(series),
        flush=True,
    )

    print(
        "📊 TGJU NORMALIZED POINTS:",
        len(normalized),
        flush=True,
    )

    print(
        "⚠️ TGJU REJECTED TIMESTAMP:",
        rejected_timestamp,
        flush=True,
    )

    print(
        "⚠️ TGJU REJECTED PRICE:",
        rejected_price,
        flush=True,
    )

    if normalized:

        print(
            "🕐 TGJU FIRST POINT:",
            normalized[0]["timestamp"].isoformat(),
            flush=True,
        )

        print(
            "🕐 TGJU LAST POINT:",
            normalized[-1]["timestamp"].isoformat(),
            flush=True,
        )

        print(
            "💰 TGJU LAST PRICE TOMAN:",
            normalized[-1]["price"],
            flush=True,
        )

    return normalized


# ============================================================
# COMPLETE CANDLE BOUNDARY
# ============================================================

def _floor_timestamp(
    timestamp: datetime,
    minutes: int,
) -> datetime:
    """
    قرار دادن timestamp روی ابتدای کندل.
    """

    timestamp = timestamp.astimezone(
        timezone.utc
    )

    minute = (
        timestamp.minute
        - (
            timestamp.minute
            % minutes
        )
    )

    return timestamp.replace(
        minute=minute,
        second=0,
        microsecond=0,
    )


# ============================================================
# BUILD CANDLES
# ============================================================

def _build_candles(
    points: List[Dict[str, Any]],
    timeframe_minutes: int,
) -> List[Dict[str, Any]]:
    """
    ساخت کندل فقط در حافظه.

    هیچ Database operation در این تابع وجود ندارد.
    """

    if not points:
        return []

    buckets: Dict[
        datetime,
        List[Dict[str, Any]],
    ] = {}

    for point in points:

        timestamp = point[
            "timestamp"
        ]

        bucket = _floor_timestamp(
            timestamp,
            timeframe_minutes,
        )

        buckets.setdefault(
            bucket,
            [],
        ).append(point)

    candles: List[
        Dict[str, Any]
    ] = []

    sorted_buckets = sorted(
        buckets.keys()
    )

    now = datetime.now(
        timezone.utc
    )

    timeframe_delta = timedelta(
        minutes=timeframe_minutes
    )

    for bucket in sorted_buckets:

        candle_end = (
            bucket
            + timeframe_delta
        )

        # ----------------------------------------------------
        # فقط کندل کاملاً بسته
        # ----------------------------------------------------

        if candle_end > now:
            continue

        bucket_points = buckets[
            bucket
        ]

        bucket_points.sort(
            key=lambda item: item[
                "timestamp"
            ]
        )

        prices = [
            point["price"]
            for point in bucket_points
        ]

        if not prices:
            continue

        candle = {
            "timestamp": bucket,
            "timestamp_ms": int(
                bucket.timestamp()
                * 1000
            ),
            "open": prices[0],
            "high": max(prices),
            "low": min(prices),
            "close": prices[-1],
            "volume": None,
            "timeframe": (
                f"{timeframe_minutes}m"
            ),
            "source": "tgju_live",
        }

        candles.append(
            candle
        )

    return candles


# ============================================================
# ONE-HOUR LIVE WINDOW
# ============================================================

def get_live_candles(
    window_minutes: int = WINDOW_MINUTES,
) -> Dict[
    str,
    List[Dict[str, Any]],
]:
    """
    دریافت مستقیم داده TGJU و ساخت کندل‌های زنده.

    مسیر:

    TGJU
      ↓
    raw intraday series
      ↓
    normalization
      ↓
    last 60 minutes
      ↓
    5m / 15m / 1h
      ↓
    RAM

    هیچ خواندن یا نوشتنی از gold_candles انجام نمی‌شود.
    """

    print(
        "📡 LIVE CANDLES: requesting TGJU...",
        flush=True,
    )

    # --------------------------------------------------------
    # 1. Request TGJU DIRECTLY
    # --------------------------------------------------------

    response = fetch_tgju_page()

    response.raise_for_status()

    print(
        "✅ LIVE CANDLES: TGJU response received.",
        flush=True,
    )

    # --------------------------------------------------------
    # 2. Extract source intraday series
    # --------------------------------------------------------

    series = extract_price_series(
        response.text
    )

    if not series:
        raise RuntimeError(
            "TGJU returned no intraday "
            "price series."
        )

    print(
        "📈 LIVE CANDLES: extracted points:",
        len(series),
        flush=True,
    )

    # --------------------------------------------------------
    # 3. Normalize timestamps and prices
    # --------------------------------------------------------

    points = _normalize_points(
        series
    )

    if not points:
        raise RuntimeError(
            "TGJU intraday series could "
            "not be normalized."
        )

    # --------------------------------------------------------
    # 4. Take ONLY the requested window
    # --------------------------------------------------------

    latest_timestamp = points[-1][
        "timestamp"
    ]

    window_start = (
        latest_timestamp
        - timedelta(
            minutes=window_minutes
        )
    )

    recent_points = [
        point
        for point in points
        if (
            point["timestamp"]
            >= window_start
        )
    ]

    print(
        "⏱️ LIVE WINDOW:",
        window_start.isoformat(),
        "→",
        latest_timestamp.isoformat(),
        flush=True,
    )

    print(
        "📊 LIVE POINTS IN WINDOW:",
        len(recent_points),
        flush=True,
    )

    if not recent_points:
        raise RuntimeError(
            "No TGJU points found inside "
            "the requested live window."
        )

    # --------------------------------------------------------
    # 5. Build candles IN MEMORY
    # --------------------------------------------------------

    candles_5m = _build_candles(
        recent_points,
        TIMEFRAMES["5m"],
    )

    candles_15m = _build_candles(
        recent_points,
        TIMEFRAMES["15m"],
    )

    candles_1h = _build_candles(
        recent_points,
        TIMEFRAMES["1h"],
    )

    # --------------------------------------------------------
    # 6. Diagnostic
    # --------------------------------------------------------

    print(
        "🕯️ LIVE CANDLES:",
        f"5m={len(candles_5m)}",
        f"15m={len(candles_15m)}",
        f"1h={len(candles_1h)}",
        flush=True,
    )

    if candles_5m:

        print(
            "🕯️ 5M FIRST:",
            candles_5m[0]["timestamp"].isoformat(),
            flush=True,
        )

        print(
            "🕯️ 5M LAST:",
            candles_5m[-1]["timestamp"].isoformat(),
            flush=True,
        )

    # --------------------------------------------------------
    # 7. Return memory objects only.
    #
    # NO database read.
    # NO database write.
    # --------------------------------------------------------

    return {
        "5m": candles_5m,
        "15m": candles_15m,
        "1h": candles_1h,
    }


# ============================================================
# DIAGNOSTIC
# ============================================================

def get_live_candle_diagnostic(
    candles: Dict[
        str,
        List[Dict[str, Any]],
    ],
) -> Dict[str, Any]:
    """
    وضعیت کندل‌های زنده.
    """

    result: Dict[
        str,
        Any,
    ] = {}

    for timeframe in (
        "5m",
        "15m",
        "1h",
    ):

        values = candles.get(
            timeframe,
            [],
        )

        result[timeframe] = {
            "count": len(values),
            "first": (
                values[0]["timestamp"].isoformat()
                if values
                else None
            ),
            "last": (
                values[-1]["timestamp"].isoformat()
                if values
                else None
            ),
        }

    return result


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "WINDOW_MINUTES",
    "TIMEFRAMES",
    "RIAL_TO_TOMAN",
    "get_live_candles",
    "get_live_candle_diagnostic",
]
