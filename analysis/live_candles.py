from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import (
    get_tgju_price_points,
    get_latest_market_snapshot,
)


# ============================================================
# CONFIG
# ============================================================

# برای ساخت حداقل 25 کندل 5 دقیقه‌ای،
# یک ساعت کافی نیست.
WINDOW_MINUTES = 180

TIMEFRAMES = {
    "5m": 5,
    "15m": 15,
    "1h": 60,
}

# حداقل کندل لازم برای تحلیل در analysis_engine.py
MIN_5M_CANDLES = 25

# محدوده مجاز قیمت نسبت به قیمت فعلی 18K
#
# اگر قیمت واقعی مثلاً:
# 239,168,000 تومان باشد
#
# داده‌ای مثل:
# 5,094,500
#
# به صورت خودکار رد می‌شود.
MIN_PRICE_RATIO = 0.70
MAX_PRICE_RATIO = 1.30


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


# ============================================================
# TIMESTAMP NORMALIZATION
# ============================================================

def _normalize_timestamp(
    value: Any,
) -> Optional[datetime]:
    """
    نرمال‌سازی timestamp به UTC.
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
# CURRENT 18K PRICE
# ============================================================

def _get_current_18k_price() -> Optional[float]:
    """
    دریافت آخرین قیمت معتبر طلای 18 عیار به تومان.

    اولویت:
    1. latest market snapshot
    2. آخرین TGJU point
    """

    # --------------------------------------------------------
    # 1. Market snapshot
    # --------------------------------------------------------

    try:
        snapshot = get_latest_market_snapshot()

        if snapshot:
            candidates = [
                snapshot.get("gold_18k_toman"),
                snapshot.get("gold_18k"),
                snapshot.get("gold_price_toman"),
            ]

            for value in candidates:
                price = _to_float(value)

                if price is not None:
                    return price

    except Exception as exc:
        print(
            "⚠️ LIVE CANDLES: market snapshot unavailable:",
            repr(exc),
            flush=True,
        )

    # --------------------------------------------------------
    # 2. Latest TGJU point
    # --------------------------------------------------------

    try:
        rows = get_tgju_price_points(
            symbol="gold_18k",
            limit=1,
        )

        if rows:
            row = rows[0]

            # expected:
            # timestamp_ms, timestamp, price
            if isinstance(row, (list, tuple)):
                if len(row) >= 3:
                    price = _to_float(
                        row[2]
                    )

                    if price is not None:
                        return price

            elif isinstance(row, dict):
                price = _to_float(
                    row.get("price")
                    or row.get("value")
                    or row.get("close")
                )

                if price is not None:
                    return price

    except Exception as exc:
        print(
            "⚠️ LIVE CANDLES: latest TGJU point unavailable:",
            repr(exc),
            flush=True,
        )

    return None


# ============================================================
# DATABASE POINT NORMALIZATION
# ============================================================

def _normalize_database_points(
    rows: List[Any],
    current_price: Optional[float],
) -> List[Dict[str, Any]]:
    """
    تبدیل نقاط database به ساختار استاندارد.

    ساختار نهایی:

    {
        timestamp,
        timestamp_ms,
        price
    }

    فقط قیمت‌های معتبر 18K پذیرفته می‌شوند.
    """

    points: List[
        Dict[str, Any]
    ] = []

    rejected_timestamp = 0
    rejected_price = 0
    rejected_outlier = 0

    # --------------------------------------------------------
    # Calculate acceptable price range
    # --------------------------------------------------------

    min_price = None
    max_price = None

    if current_price is not None:
        min_price = (
            current_price
            * MIN_PRICE_RATIO
        )

        max_price = (
            current_price
            * MAX_PRICE_RATIO
        )

        print(
            "💰 LIVE PRICE REFERENCE:",
            f"{current_price:,.0f}",
            "TOMAN",
            flush=True,
        )

        print(
            "🛡️ VALID PRICE RANGE:",
            f"{min_price:,.0f}",
            "→",
            f"{max_price:,.0f}",
            "TOMAN",
            flush=True,
        )

    # --------------------------------------------------------
    # Process database rows
    # --------------------------------------------------------

    for row in rows:

        timestamp_value = None
        price_value = None

        # ----------------------------------------------------
        # Tuple / list
        # ----------------------------------------------------

        if isinstance(
            row,
            (list, tuple),
        ):
            # database.py:
            # (timestamp_ms, timestamp, price)

            if len(row) >= 3:
                timestamp_value = row[1]
                price_value = row[2]

        # ----------------------------------------------------
        # Dict
        # ----------------------------------------------------

        elif isinstance(
            row,
            dict,
        ):
            timestamp_value = (
                row.get("timestamp")
                or row.get("time")
                or row.get("datetime")
                or row.get("created_at")
            )

            price_value = (
                row.get("price")
                or row.get("value")
                or row.get("close")
                or row.get("last")
            )

        else:
            continue

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        timestamp = _normalize_timestamp(
            timestamp_value
        )

        if timestamp is None:
            rejected_timestamp += 1
            continue

        # ----------------------------------------------------
        # Price
        # ----------------------------------------------------

        price = _to_float(
            price_value
        )

        if price is None:
            rejected_price += 1
            continue

        # ----------------------------------------------------
        # IMPORTANT:
        # Reject obviously wrong series.
        # ----------------------------------------------------

        if (
            min_price is not None
            and max_price is not None
        ):
            if (
                price < min_price
                or price > max_price
            ):
                rejected_outlier += 1
                continue

        # ----------------------------------------------------
        # Accept
        # ----------------------------------------------------

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
    # Diagnostics
    # --------------------------------------------------------

    print(
        "📊 DATABASE TGJU RAW ROWS:",
        len(rows),
        flush=True,
    )

    print(
        "📊 VALID 18K POINTS:",
        len(normalized),
        flush=True,
    )

    print(
        "⚠️ REJECTED TIMESTAMP:",
        rejected_timestamp,
        flush=True,
    )

    print(
        "⚠️ REJECTED PRICE:",
        rejected_price,
        flush=True,
    )

    print(
        "🛡️ REJECTED OUTLIERS:",
        rejected_outlier,
        flush=True,
    )

    if normalized:
        print(
            "🕐 FIRST VALID POINT:",
            normalized[0]["timestamp"].isoformat(),
            flush=True,
        )

        print(
            "🕐 LAST VALID POINT:",
            normalized[-1]["timestamp"].isoformat(),
            flush=True,
        )

        print(
            "💰 LAST VALID PRICE:",
            f"{normalized[-1]['price']:,.0f}",
            "TOMAN",
            flush=True,
        )

    return normalized


# ============================================================
# CANDLE BOUNDARY
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
    ساخت کندل در RAM.

    هیچ Database operation ندارد.
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

    now = datetime.now(
        timezone.utc
    )

    timeframe_delta = timedelta(
        minutes=timeframe_minutes
    )

    for bucket in sorted(
        buckets.keys()
    ):

        candle_end = (
            bucket
            + timeframe_delta
        )

        # فقط کندل کاملاً بسته
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

        candles.append(
            {
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
        )

    return candles


# ============================================================
# LIVE CANDLES
# ============================================================

def get_live_candles(
    window_minutes: int = WINDOW_MINUTES,
) -> Dict[
    str,
    List[Dict[str, Any]],
]:
    """
    ساخت کندل‌های زنده 18K از داده‌های معتبر ذخیره‌شده.

    مسیر:

    TGJU CALL5
        ↓
    tgju_price_points
        ↓
    price validation
        ↓
    live window
        ↓
    5m / 15m / 1h

    هیچ gold-chart / geram18 مستقیماً خوانده نمی‌شود.
    """

    print(
        "📡 LIVE CANDLES: reading stored TGJU points...",
        flush=True,
    )

    # --------------------------------------------------------
    # 1. Current valid 18K price
    # --------------------------------------------------------

    current_price = (
        _get_current_18k_price()
    )

    if current_price is None:
        raise RuntimeError(
            "Could not determine current "
            "18K gold price."
        )

    # --------------------------------------------------------
    # 2. Read TGJU points
    #
    # 180 minutes + safety margin
    # --------------------------------------------------------

    requested_limit = 5000

    try:
        rows = get_tgju_price_points(
            symbol="gold_18k",
            limit=requested_limit,
        )

    except Exception as exc:
        print(
            "❌ LIVE CANDLES: database read failed:",
            repr(exc),
            flush=True,
        )

        raise RuntimeError(
            "Could not read TGJU price points."
        ) from exc

    if not rows:
        raise RuntimeError(
            "No TGJU price points available."
        )

    # --------------------------------------------------------
    # 3. Normalize + validate
    # --------------------------------------------------------

    points = _normalize_database_points(
        rows,
        current_price,
    )

    if not points:
        raise RuntimeError(
            "No valid 18K TGJU points "
            "remain after price validation."
        )

    # --------------------------------------------------------
    # 4. Determine latest point
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
        "📊 VALID POINTS IN WINDOW:",
        len(recent_points),
        flush=True,
    )

    # --------------------------------------------------------
    # 5. Build candles
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
    # 6. Diagnostics
    # --------------------------------------------------------

    print(
        "🕯️ LIVE CANDLES:",
        f"5m={len(candles_5m)}",
        f"15m={len(candles_15m)}",
        f"1h={len(candles_1h)}",
        flush=True,
    )

    # --------------------------------------------------------
    # 5m diagnostics
    # --------------------------------------------------------

    if candles_5m:

        print(
            "🕯️ 5M FIRST:",
            candles_5m[0][
                "timestamp"
            ].isoformat(),
            flush=True,
        )

        print(
            "🕯️ 5M LAST:",
            candles_5m[-1][
                "timestamp"
            ].isoformat(),
            flush=True,
        )

        print(
            "💰 5M LAST CLOSE:",
            f"{candles_5m[-1]['close']:,.0f}",
            "TOMAN",
            flush=True,
        )

    # --------------------------------------------------------
    # 7. Analysis readiness
    # --------------------------------------------------------

    if len(candles_5m) < MIN_5M_CANDLES:

        print(
            "ℹ️ ANALYSIS: not enough 5m candles",
            f"({len(candles_5m)}/{MIN_5M_CANDLES})",
            flush=True,
        )

    else:

        print(
            "✅ ANALYSIS: enough 5m candles",
            f"({len(candles_5m)}/{MIN_5M_CANDLES})",
            flush=True,
        )

    # --------------------------------------------------------
    # 8. Return
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
                values[0][
                    "timestamp"
                ].isoformat()
                if values
                else None
            ),
            "last": (
                values[-1][
                    "timestamp"
                ].isoformat()
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
    "MIN_5M_CANDLES",
    "MIN_PRICE_RATIO",
    "MAX_PRICE_RATIO",
    "get_live_candles",
    "get_live_candle_diagnostic",
]
