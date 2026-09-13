"""
Live analysis adapter for Iran Gold AI.

این ماژول داده‌های یک ساعت اخیر TGJU را از طریق
analysis.live_candles دریافت می‌کند و کندل‌های
5m / 15m / 1h را فقط در حافظه در اختیار موتور تحلیل
قرار می‌دهد.

هیچ خواندن یا نوشتنی روی جدول gold_candles انجام نمی‌شود.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from analysis.live_candles import get_live_candles


# ============================================================
# CONFIG
# ============================================================

LIVE_WINDOW_MINUTES = 60

TIMEFRAMES = (
    "5m",
    "15m",
    "1h",
)


# ============================================================
# HELPERS
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

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _normalize_candle(
    candle: Any,
) -> Optional[Dict[str, Any]]:
    """
    نرمال‌سازی یک کندل.
    """

    if not isinstance(
        candle,
        dict,
    ):
        return None

    result = dict(candle)

    numeric_fields = (
        "open",
        "high",
        "low",
        "close",
        "volume",
    )

    for field in numeric_fields:

        if field in result:

            result[field] = _to_float(
                result[field]
            )

    # کندل بدون close قابل استفاده نیست
    if result.get("close") is None:
        return None

    return result


def _normalize_timeframe(
    candles: Any,
) -> List[Dict[str, Any]]:
    """
    نرمال‌سازی تمام کندل‌های یک تایم‌فریم.
    """

    result: List[Dict[str, Any]] = []

    for candle in candles or []:

        normalized = _normalize_candle(
            candle
        )

        if normalized is None:
            continue

        result.append(
            normalized
        )

    return result


# ============================================================
# LIVE CANDLES
# ============================================================

def get_live_analysis_candles(
    window_minutes: int = LIVE_WINDOW_MINUTES,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    دریافت کندل‌های زنده از منبع TGJU.

    داده‌ها:
        5m
        15m
        1h

    نکته:
    هیچ داده‌ای در این مرحله از gold_candles خوانده نمی‌شود.
    """

    live = get_live_candles(
        window_minutes=window_minutes,
    )

    return {
        timeframe: _normalize_timeframe(
            live.get(
                timeframe,
                [],
            )
        )
        for timeframe in TIMEFRAMES
    }


# ============================================================
# STATUS
# ============================================================

def get_live_analysis_status(
    candles: Dict[
        str,
        List[Dict[str, Any]],
    ],
) -> Dict[str, Any]:
    """
    ایجاد وضعیت داده‌های زنده برای دیباگ و کنترل تحلیل.
    """

    counts = {
        timeframe: len(
            candles.get(
                timeframe,
                [],
            )
        )
        for timeframe in TIMEFRAMES
    }

    available = {
        timeframe: (
            counts[timeframe] > 0
        )
        for timeframe in TIMEFRAMES
    }

    return {
        "mode": "live_memory",

        "window_minutes": (
            LIVE_WINDOW_MINUTES
        ),

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "counts": counts,

        "available": available,

        "has_5m": available["5m"],

        "has_15m": available["15m"],

        "has_1h": available["1h"],
    }


# ============================================================
# PREPARE LIVE ANALYSIS
# ============================================================

def prepare_live_analysis(
    window_minutes: int = LIVE_WINDOW_MINUTES,
) -> Dict[str, Any]:
    """
    آماده‌سازی کامل داده برای تحلیل زنده.

    خروجی:

    {
        "candles": {
            "5m": [...],
            "15m": [...],
            "1h": [...]
        },

        "status": {
            ...
        }
    }
    """

    candles = get_live_analysis_candles(
        window_minutes=window_minutes,
    )

    status = get_live_analysis_status(
        candles
    )

    return {
        "candles": candles,
        "status": status,
    }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "LIVE_WINDOW_MINUTES",
    "TIMEFRAMES",
    "get_live_analysis_candles",
    "get_live_analysis_status",
    "prepare_live_analysis",
]
