from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

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

def _to_float(value: Any):
    try:
        if value is None:
            return None

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
) -> datetime | None:

    if isinstance(
        value,
        datetime,
    ):
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value

    if isinstance(
        value,
        (int, float),
    ):
        try:
            return datetime.fromtimestamp(
                float(value),
                tz=timezone.utc,
            )
        except Exception:
            return None

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        return datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )
    except Exception:
        return None


# ============================================================
# RAW POINT NORMALIZATION
# ============================================================

def _normalize_points(
    series: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    points = []

    for item in series:

        if not isinstance(
            item,
            dict,
        ):
            continue

        timestamp = _normalize_timestamp(
            item.get("timestamp")
            or item.get("time")
            or item.get("datetime")
        )

        price = _to_float(
            item.get("price")
        )

        if (
            timestamp is None
            or price is None
        ):
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
    # Remove duplicate timestamps
    # Keep latest value.
    # --------------------------------------------------------

    unique = {}

    for point in points:

        unique[
            point["timestamp_ms"]
        ] = point

    return list(
        sorted(
            unique.values(),
            key=lambda item: item[
                "timestamp"
            ],
        )
    )


# ============================================================
# COMPLETE CANDLE BOUNDARY
# ============================================================

def _floor_timestamp(
    timestamp: datetime,
    minutes: int,
) -> datetime:

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

    candles = []

    sorted_buckets = sorted(
        buckets.keys()
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Only COMPLETED candles are returned.
    #
    # The current unfinished candle is ignored.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 1. Request TGJU DIRECTLY
    # --------------------------------------------------------

    response = fetch_tgju_page()

    response.raise_for_status()

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

    # --------------------------------------------------------
    # 3. Normalize prices and timestamps
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
    # 4. Take ONLY the last requested hour
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
        5,
    )

    candles_15m = _build_candles(
        recent_points,
        15,
    )

    candles_1h = _build_candles(
        recent_points,
        60,
    )

    # --------------------------------------------------------
    # 6. Return only memory objects.
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

    result = {}

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
