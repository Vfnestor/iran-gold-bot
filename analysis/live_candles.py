# analysis/live_candles.py

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any


# ============================================================
# CONFIG
# ============================================================

LIVE_WINDOW_MINUTES = 180

MIN_5M_CANDLES = 25

# محدوده محافظه‌کارانه برای قیمت طلای 18 عیار
MIN_VALID_18K_PRICE = 50_000_000
MAX_VALID_18K_PRICE = 1_000_000_000


# ============================================================
# HELPERS
# ============================================================

def _to_datetime(value: Any) -> datetime | None:
    """
    تبدیل timestampهای مختلف به datetime timezone-aware.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(
                float(value),
                tz=timezone.utc,
            )
        except Exception:
            return None

    if isinstance(value, str):
        text = value.strip()

        if not text:
            return None

        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"

            dt = datetime.fromisoformat(text)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(timezone.utc)

        except Exception:
            pass

        try:
            return datetime.fromtimestamp(
                float(text),
                tz=timezone.utc,
            )
        except Exception:
            return None

    return None


def _extract_price(row: Any) -> float | None:
    """
    استخراج قیمت از ساختارهای مختلف دیتابیس.
    """

    if isinstance(row, dict):

        possible_keys = (
            "price",
            "value",
            "gold_18k_toman",
            "geram18",
            "close",
            "last",
        )

        for key in possible_keys:
            value = row.get(key)

            if value is None:
                continue

            try:
                price = float(value)

                if price > 0:
                    return price

            except (TypeError, ValueError):
                continue

    elif isinstance(row, (list, tuple)):

        # ساختارهای رایج:
        # (timestamp, price)
        # (id, timestamp, price)
        # ...

        for value in reversed(row):

            try:
                price = float(value)

                if (
                    MIN_VALID_18K_PRICE
                    <= price
                    <= MAX_VALID_18K_PRICE
                ):
                    return price

            except (TypeError, ValueError):
                continue

    else:

        try:
            price = float(row)

            if (
                MIN_VALID_18K_PRICE
                <= price
                <= MAX_VALID_18K_PRICE
            ):
                return price

        except (TypeError, ValueError):
            pass

    return None


def _extract_timestamp(row: Any) -> datetime | None:
    """
    استخراج زمان از ساختارهای مختلف دیتابیس.
    """

    if isinstance(row, dict):

        possible_keys = (
            "timestamp",
            "time",
            "created_at",
            "datetime",
            "date",
        )

        for key in possible_keys:

            value = row.get(key)

            if value is None:
                continue

            dt = _to_datetime(value)

            if dt is not None:
                return dt

    elif isinstance(row, (list, tuple)):

        # معمولاً timestamp در یکی از موقعیت‌های ابتدایی است.
        for value in row[:3]:

            dt = _to_datetime(value)

            if dt is not None:
                return dt

    return None


def _normalize_point(row: Any) -> dict[str, Any] | None:
    """
    تبدیل رکورد خام به:

    {
        "timestamp": datetime,
        "price": float
    }
    """

    timestamp = _extract_timestamp(row)
    price = _extract_price(row)

    if timestamp is None or price is None:
        return None

    if not (
        MIN_VALID_18K_PRICE
        <= price
        <= MAX_VALID_18K_PRICE
    ):
        return None

    return {
        "timestamp": timestamp,
        "price": price,
    }


def _floor_time(timestamp: datetime, minutes: int) -> datetime:
    """
    قرار دادن timestamp در ابتدای کندل.
    """

    timestamp = timestamp.astimezone(timezone.utc)

    total_minutes = (
        timestamp.hour * 60
        + timestamp.minute
    )

    floored_minutes = (
        total_minutes // minutes
    ) * minutes

    hour = floored_minutes // 60
    minute = floored_minutes % 60

    return timestamp.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )


def _build_candles(
    points: list[dict[str, Any]],
    timeframe_minutes: int,
) -> list[dict[str, Any]]:
    """
    ساخت کندل OHLC از نقاط معتبر.
    """

    buckets: dict[
        datetime,
        list[float],
    ] = defaultdict(list)

    for point in points:

        timestamp = point["timestamp"]
        price = point["price"]

        bucket = _floor_time(
            timestamp,
            timeframe_minutes,
        )

        buckets[bucket].append(price)

    candles: list[dict[str, Any]] = []

    for bucket in sorted(buckets.keys()):

        prices = buckets[bucket]

        if not prices:
            continue

        candles.append(
            {
                "timestamp": bucket,
                "open": prices[0],
                "high": max(prices),
                "low": min(prices),
                "close": prices[-1],
            }
        )

    return candles


# ============================================================
# DATABASE IMPORT
# ============================================================

def _load_raw_points() -> list[Any]:
    """
    دریافت نقاط خام TGJU از دیتابیس.

    این تابع چند نام رایج برای API دیتابیس را
    پشتیبانی می‌کند تا وابستگی به یک امضای خاص کمتر شود.
    """

    try:

        from database import get_tgju_price_history

        rows = get_tgju_price_history()

        if rows is None:
            return []

        if isinstance(rows, list):
            return rows

        if isinstance(rows, tuple):
            return list(rows)

        return list(rows)

    except ImportError:
        pass

    except Exception as exc:

        print(
            "⚠️ LIVE CANDLES: "
            f"database history unavailable: {exc!r}"
        )

    # fallback
    try:

        from database import get_market_history

        rows = get_market_history()

        if rows is None:
            return []

        if isinstance(rows, list):
            return rows

        if isinstance(rows, tuple):
            return list(rows)

        return list(rows)

    except Exception as exc:

        print(
            "⚠️ LIVE CANDLES: "
            f"market history unavailable: {exc!r}"
        )

        return []


# ============================================================
# LIVE CANDLE ENGINE
# ============================================================

def get_live_candles(
    window_minutes: int = LIVE_WINDOW_MINUTES,
) -> dict[str, list[dict[str, Any]]]:
    """
    ساخت کندل‌های زنده فقط از نقاط معتبر طلای 18 عیار.

    خروجی:

    {
        "5m": [...],
        "15m": [...],
        "1h": [...]
    }

    نکته مهم:
    داده‌های قدیمی/نامعتبر TGJU که قیمت آنها با قیمت واقعی
    طلای 18 عیار همخوانی ندارد، حذف می‌شوند.
    """

    now = datetime.now(timezone.utc)

    window_start = (
        now - timedelta(minutes=window_minutes)
    )

    # --------------------------------------------------------
    # RAW DATABASE POINTS
    # --------------------------------------------------------

    raw_rows = _load_raw_points()

    print(
        "📊 DATABASE TGJU RAW ROWS:",
        len(raw_rows),
    )

    valid_points: list[dict[str, Any]] = []

    skipped_invalid = 0
    skipped_old = 0

    # --------------------------------------------------------
    # NORMALIZE + FILTER
    # --------------------------------------------------------

    for row in raw_rows:

        point = _normalize_point(row)

        if point is None:

            skipped_invalid += 1
            continue

        timestamp = point["timestamp"]
        price = point["price"]

        # فقط بازه زنده
        if timestamp < window_start:

            skipped_old += 1
            continue

        # کنترل نهایی قیمت
        if not (
            MIN_VALID_18K_PRICE
            <= price
            <= MAX_VALID_18K_PRICE
        ):

            skipped_invalid += 1
            continue

        valid_points.append(point)

    # --------------------------------------------------------
    # SORT + DEDUP
    # --------------------------------------------------------

    valid_points.sort(
        key=lambda item: item["timestamp"]
    )

    deduped: list[dict[str, Any]] = []

    seen: set[tuple[datetime, float]] = set()

    for point in valid_points:

        key = (
            point["timestamp"],
            point["price"],
        )

        if key in seen:
            continue

        seen.add(key)
        deduped.append(point)

    valid_points = deduped

    # --------------------------------------------------------
    # LOGGING
    # --------------------------------------------------------

    if valid_points:

        first_point = valid_points[0]
        last_point = valid_points[-1]

        print(
            "🕐 FIRST VALID POINT:",
            first_point["timestamp"].isoformat(),
        )

        print(
            "🕐 LAST VALID POINT:",
            last_point["timestamp"].isoformat(),
        )

        print(
            "💰 LAST VALID PRICE:",
            f"{last_point['price']:,.0f}",
            "TOMAN",
        )

    else:

        print(
            "⚠️ NO VALID LIVE 18K POINTS"
        )

    print(
        "⚠️ SKIPPED INVALID:",
        skipped_invalid,
    )

    print(
        "⏳ SKIPPED OLD:",
        skipped_old,
    )

    print(
        "⏱️ LIVE WINDOW:",
        window_start.isoformat(),
        "→",
        now.isoformat(),
    )

    print(
        "📊 VALID POINTS IN WINDOW:",
        len(valid_points),
    )

    # --------------------------------------------------------
    # BUILD CANDLES
    # --------------------------------------------------------

    candles_5m = _build_candles(
        valid_points,
        5,
    )

    candles_15m = _build_candles(
        valid_points,
        15,
    )

    candles_1h = _build_candles(
        valid_points,
        60,
    )

    print(
        "🕯️ LIVE CANDLES:",
        f"5m={len(candles_5m)}",
        f"15m={len(candles_15m)}",
        f"1h={len(candles_1h)}",
    )

    # --------------------------------------------------------
    # ANALYSIS STATUS
    # --------------------------------------------------------

    if len(candles_5m) < MIN_5M_CANDLES:

        print(
            "ℹ️ ANALYSIS: "
            f"not enough 5m candles "
            f"({len(candles_5m)}/{MIN_5M_CANDLES})"
        )

    else:

        print(
            "🟢 ANALYSIS: "
            f"enough 5m candles "
            f"({len(candles_5m)}/{MIN_5M_CANDLES})"
        )

    return {
        "5m": candles_5m,
        "15m": candles_15m,
        "1h": candles_1h,
    }


# ============================================================
# PUBLIC API
# ============================================================

def get_live_candles_with_status(
    window_minutes: int = LIVE_WINDOW_MINUTES,
) -> dict[str, Any]:
    """
    نسخه‌ای که علاوه بر کندل‌ها، وضعیت داده را هم برمی‌گرداند.
    """

    candles = get_live_candles(
        window_minutes=window_minutes,
    )

    count_5m = len(candles.get("5m", []))

    return {
        "candles": candles,
        "ready": count_5m >= MIN_5M_CANDLES,
        "5m_count": count_5m,
        "15m_count": len(candles.get("15m", [])),
        "1h_count": len(candles.get("1h", [])),
        "minimum_5m": MIN_5M_CANDLES,
    }


# ============================================================
# DEBUG / MANUAL TEST
# ============================================================

if __name__ == "__main__":

    result = get_live_candles()

    print()
    print("========== LIVE CANDLE TEST ==========")

    for timeframe in ("5m", "15m", "1h"):

        candles = result.get(
            timeframe,
            [],
        )

        print(
            f"{timeframe}: {len(candles)} candles"
        )

        if candles:

            latest = candles[-1]

            print(
                "   latest:",
                latest,
            )
