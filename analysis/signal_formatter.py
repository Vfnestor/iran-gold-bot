from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


# ============================================================
# CONFIG
# ============================================================

SYMBOL = "gold_18k"
TIMEFRAME = "15m"

# تعداد کندل‌هایی که برای بررسی احتمال برخورد اهداف
# در صورت وجود داده تاریخی استفاده می‌شود.
LOOKAHEAD_CANDLES = 12

# حداقل تعداد نمونه تاریخی واقعی برای محاسبه احتمال
MIN_HISTORY_SAMPLES = 20

# فاصله اهداف بر اساس ATR
TARGET_ATR_MULTIPLIERS = (
    0.50,
    1.00,
    1.50,
    2.00,
    2.50,
)

# حد ضرر
STOP_ATR_MULTIPLIER = 1.20


# ============================================================
# LIVE IN-MEMORY CANDLES
# ============================================================
#
# این متغیر عمداً در حافظه است.
#
# هیچ candle از database خوانده یا ذخیره نمی‌شود.
#
# ساختار:
#
# {
#     "5m": [...],
#     "15m": [...],
#     "1h": [...]
# }
#
# فایل/ماژول بعدی این داده‌ها را هنگام درخواست تحلیل
# از منبع زنده وارد خواهد کرد.
#
# ============================================================

_LIVE_CANDLES: Dict[str, List[Dict[str, Any]]] = {
    "5m": [],
    "15m": [],
    "1h": [],
}


def set_live_candles(
    candles: Dict[str, Iterable[Dict[str, Any]]],
) -> None:
    """
    قرار دادن کندل‌های زنده در حافظه.

    این تابع هیچ عملیات دیتابیسی انجام نمی‌دهد.
    """

    global _LIVE_CANDLES

    normalized: Dict[str, List[Dict[str, Any]]] = {
        "5m": [],
        "15m": [],
        "1h": [],
    }

    for timeframe in normalized:
        values = candles.get(timeframe, [])

        if values is None:
            continue

        for candle in values:
            if isinstance(candle, dict):
                normalized[timeframe].append(
                    dict(candle)
                )

    for timeframe in normalized:
        normalized[timeframe].sort(
            key=_candle_timestamp
        )

    _LIVE_CANDLES = normalized


def get_live_candles(
    timeframe: str = TIMEFRAME,
) -> List[Dict[str, Any]]:
    """
    دریافت کندل‌های زنده از حافظه.

    مهم:
    این تابع به database دست نمی‌زند.
    """

    candles = _LIVE_CANDLES.get(
        timeframe,
        [],
    )

    return [
        dict(candle)
        for candle in candles
        if isinstance(candle, dict)
    ]


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize_candle(
    candle: Dict[str, Any],
) -> Dict[str, Any]:
    """
    نرمال‌سازی یک کندل.

    کلیدهای مختلف احتمالی را پشتیبانی می‌کند:
        open / o
        high / h
        low / l
        close / c
        timestamp / time / datetime / start_time
    """

    result = dict(candle)

    result["open"] = _number(
        candle.get(
            "open",
            candle.get("o"),
        )
    )

    result["high"] = _number(
        candle.get(
            "high",
            candle.get("h"),
        )
    )

    result["low"] = _number(
        candle.get(
            "low",
            candle.get("l"),
        )
    )

    result["close"] = _number(
        candle.get(
            "close",
            candle.get("c"),
        )
    )

    result["_timestamp"] = _candle_timestamp(
        candle
    )

    return result


def _normalize_candles(
    candles: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    نرمال‌سازی و مرتب‌سازی کندل‌ها.
    """

    normalized: List[Dict[str, Any]] = []

    for candle in candles:
        if not isinstance(candle, dict):
            continue

        try:
            item = _normalize_candle(candle)

            if (
                item["open"] is None
                or item["high"] is None
                or item["low"] is None
                or item["close"] is None
            ):
                continue

            normalized.append(item)

        except Exception:
            continue

    normalized.sort(
        key=lambda item: item["_timestamp"]
    )

    return normalized


# ============================================================
# NUMBERS / DATETIME
# ============================================================

def _number(value: Any) -> Optional[float]:
    """
    تبدیل مقدار به float.
    """

    if value is None:
        return None

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _candle_timestamp(
    candle: Dict[str, Any],
) -> datetime:
    """
    استخراج زمان کندل.

    از چند نام رایج پشتیبانی می‌شود.
    """

    value = (
        candle.get("timestamp")
        or candle.get("time")
        or candle.get("datetime")
        or candle.get("start_time")
        or candle.get("created_at")
    )

    if isinstance(value, datetime):
        return value

    if value is None:
        return datetime.min

    if isinstance(value, (int, float)):
        try:
            # timestamp برحسب ثانیه
            return datetime.fromtimestamp(
                float(value)
            )
        except Exception:
            return datetime.min

    text = str(value).strip()

    if not text:
        return datetime.min

    # ISO format
    try:
        return datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )
    except Exception:
        pass

    # فرمت‌های رایج دیگر
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
    )

    for fmt in formats:
        try:
            return datetime.strptime(
                text,
                fmt,
            )
        except Exception:
            continue

    return datetime.min


# ============================================================
# ATR
# ============================================================

def _calculate_atr(
    candles: List[Dict[str, Any]],
    period: int = 14,
) -> Optional[float]:
    """
    محاسبه ATR به صورت ساده بر اساس True Range.

    اگر داده کافی نباشد None برمی‌گرداند.
    """

    if len(candles) < 2:
        return None

    true_ranges: List[float] = []

    previous_close: Optional[float] = None

    for candle in candles:
        high = candle.get("high")
        low = candle.get("low")
        close = candle.get("close")

        if (
            high is None
            or low is None
            or close is None
        ):
            continue

        high = float(high)
        low = float(low)
        close = float(close)

        if previous_close is None:
            true_range = high - low
        else:
            true_range = max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )

        true_ranges.append(
            max(true_range, 0.0)
        )

        previous_close = close

    if len(true_ranges) < period:
        return None

    recent = true_ranges[-period:]

    return sum(recent) / len(recent)


# ============================================================
# PRICE / FORMAT
# ============================================================

def _round_price(value: float) -> int:
    """
    قیمت خروجی را به عدد صحیح تومان تبدیل می‌کند.
    """

    return int(round(float(value)))


def _format_price(value: Optional[float]) -> str:
    """
    نمایش قیمت به تومان با جداکننده هزارگان.
    """

    if value is None:
        return "نامشخص"

    return f"{_round_price(value):,}"


# ============================================================
# SIGNAL
# ============================================================

def _extract_signal(
    analysis: Dict[str, Any],
) -> str:
    """
    استخراج نوع سیگنال از خروجی analysis_engine.
    """

    signal = (
        analysis.get("signal")
        or analysis.get("trade_signal")
        or analysis.get("direction")
        or analysis.get("recommendation")
        or "HOLD"
    )

    return str(signal).upper().strip()


def _is_buy_signal(signal: str) -> bool:
    return signal in {
        "BUY",
        "STRONG BUY",
        "LONG",
        "BULLISH",
        "🟢 BUY",
    }


def _is_sell_signal(signal: str) -> bool:
    return signal in {
        "SELL",
        "STRONG SELL",
        "SHORT",
        "BEARISH",
        "🔴 SELL",
    }


# ============================================================
# ENTRY
# ============================================================

def _get_entry_price(
    analysis: Dict[str, Any],
    candles: List[Dict[str, Any]],
) -> Optional[float]:
    """
    قیمت ورود را از analysis می‌گیرد.
    اگر وجود نداشت، آخرین close استفاده می‌شود.
    """

    candidates = (
        analysis.get("entry"),
        analysis.get("entry_price"),
        analysis.get("price"),
        analysis.get("current_price"),
    )

    trade_levels = analysis.get(
        "trade_levels"
    )

    if isinstance(trade_levels, dict):
        candidates += (
            trade_levels.get("entry"),
            trade_levels.get("entry_price"),
        )

    for value in candidates:
        number = _number(value)

        if number is not None and number > 0:
            return number

    if candles:
        close = _number(
            candles[-1].get("close")
        )

        if close is not None and close > 0:
            return close

    return None


# ============================================================
# TRADE LEVELS
# ============================================================

def _calculate_trade_levels(
    analysis: Dict[str, Any],
    candles: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    تولید Entry / Stop / TP1..TP5.

    اولویت:
    1. مقادیر معتبر موجود در analysis
    2. ATR واقعی از کندل‌های زنده
    """

    entry = _get_entry_price(
        analysis,
        candles,
    )

    if entry is None:
        return {
            "entry": None,
            "stop": None,
            "targets": [],
            "atr": None,
        }

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    atr = None

    indicators = analysis.get(
        "indicators"
    )

    if isinstance(indicators, dict):
        atr = _number(
            indicators.get("atr")
            or indicators.get("ATR")
            or indicators.get("atr14")
            or indicators.get("ATR14")
        )

    if atr is None:
        atr = _number(
            analysis.get("atr")
            or analysis.get("ATR")
        )

    if atr is None:
        atr = _calculate_atr(
            candles,
            period=14,
        )

    if atr is None or atr <= 0:
        return {
            "entry": entry,
            "stop": None,
            "targets": [],
            "atr": None,
        }

    # --------------------------------------------------------
    # Direction
    # --------------------------------------------------------

    signal = _extract_signal(
        analysis
    )

    is_buy = _is_buy_signal(signal)
    is_sell = _is_sell_signal(signal)

    # اگر سیگنال مشخص نیست، جهت تحلیل را بررسی کن.
    if not is_buy and not is_sell:
        trend = str(
            analysis.get("trend", "")
        ).upper()

        if "BULL" in trend or "UP" in trend:
            is_buy = True

        elif (
            "BEAR" in trend
            or "DOWN" in trend
        ):
            is_sell = True

    # HOLD
    if not is_buy and not is_sell:
        return {
            "entry": entry,
            "stop": None,
            "targets": [],
            "atr": atr,
        }

    stop_distance = (
        atr * STOP_ATR_MULTIPLIER
    )

    targets: List[float] = []

    for multiplier in TARGET_ATR_MULTIPLIERS:
        distance = atr * multiplier

        if is_buy:
            target = entry + distance
        else:
            target = entry - distance

        targets.append(
            max(target, 0)
        )

    if is_buy:
        stop = max(
            entry - stop_distance,
            0,
        )
    else:
        stop = max(
            entry + stop_distance,
            0,
        )

    return {
        "entry": entry,
        "stop": stop,
        "targets": targets,
        "atr": atr,
    }


# ============================================================
# HISTORICAL TARGET PROBABILITY
# ============================================================

def _target_probability(
    candles: List[Dict[str, Any]],
    target_distance: float,
    stop_distance: float,
    direction: str,
) -> Optional[float]:
    """
    محاسبه احتمال تاریخی برخورد به هدف.

    نکته مهم:
    این تابع فقط از داده واقعی استفاده می‌کند.

    اگر نمونه تاریخی کافی نباشد:
        None

    برمی‌گرداند و هیچ درصد ساختگی تولید نمی‌شود.
    """

    if len(candles) < (
        MIN_HISTORY_SAMPLES
        + LOOKAHEAD_CANDLES
    ):
        return None

    wins = 0
    total = 0

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    is_buy = _is_buy_signal(
        direction
    )

    is_sell = _is_sell_signal(
        direction
    )

    if not is_buy and not is_sell:
        return None

    max_start = (
        len(candles)
        - LOOKAHEAD_CANDLES
    )

    for index in range(
        0,
        max_start,
    ):
        entry = _number(
            candles[index].get(
                "close"
            )
        )

        if entry is None:
            continue

        if is_buy:
            target_price = (
                entry + target_distance
            )

            stop_price = (
                entry - stop_distance
            )
        else:
            target_price = (
                entry - target_distance
            )

            stop_price = (
                entry + stop_distance
            )

        result = None

        for future_index in range(
            index + 1,
            min(
                index
                + 1
                + LOOKAHEAD_CANDLES,
                len(candles),
            ),
        ):
            future = candles[
                future_index
            ]

            high = _number(
                future.get("high")
            )

            low = _number(
                future.get("low")
            )

            if high is None or low is None:
                continue

            # ------------------------------------------------
            # BUY
            # ------------------------------------------------

            if is_buy:

                target_hit = (
                    high >= target_price
                )

                stop_hit = (
                    low <= stop_price
                )

                if target_hit and stop_hit:
                    # اگر هر دو در یک کندل لمس شوند،
                    # ترتیب دقیق برخورد از OHLC مشخص نیست.
                    # بنابراین این نمونه را حذف می‌کنیم.
                    result = None
                    break

                if target_hit:
                    result = True
                    break

                if stop_hit:
                    result = False
                    break

            # ------------------------------------------------
            # SELL
            # ------------------------------------------------

            else:

                target_hit = (
                    low <= target_price
                )

                stop_hit = (
                    high >= stop_price
                )

                if target_hit and stop_hit:
                    result = None
                    break

                if target_hit:
                    result = True
                    break

                if stop_hit:
                    result = False
                    break

        if result is None:
            continue

        total += 1

        if result:
            wins += 1

    if total < MIN_HISTORY_SAMPLES:
        return None

    probability = (
        wins / total
    ) * 100.0

    return round(
        probability,
        1,
    )


def _calculate_target_probabilities(
    candles: List[Dict[str, Any]],
    atr: Optional[float],
    direction: str,
) -> List[Optional[float]]:
    """
    محاسبه احتمال تاریخی برای TP1 تا TP5.
    """

    if atr is None or atr <= 0:
        return [
            None
            for _ in TARGET_ATR_MULTIPLIERS
        ]

    stop_distance = (
        atr * STOP_ATR_MULTIPLIER
    )

    probabilities: List[
        Optional[float]
    ] = []

    for multiplier in TARGET_ATR_MULTIPLIERS:

        target_distance = (
            atr * multiplier
        )

        probability = (
            _target_probability(
                candles=candles,
                target_distance=target_distance,
                stop_distance=stop_distance,
                direction=direction,
            )
        )

        probabilities.append(
            probability
        )

    return probabilities


# ============================================================
# PROBABILITY FORMAT
# ============================================================

def _format_probability(
    probability: Optional[float],
) -> str:
    """
    اگر احتمال واقعی موجود نباشد، درصد جعلی نمایش نمی‌دهد.
    """

    if probability is None:
        return "داده تاریخی کافی نیست"

    return f"{probability:.0f}٪"


# ============================================================
# SIGNAL ID
# ============================================================

def _build_signal_id(
    candles: List[Dict[str, Any]],
) -> str:
    """
    ساخت شناسه سیگنال.

    مثال:
        #TALA18_15MIN_09120830
    """

    if candles:
        timestamp = candles[-1].get(
            "_timestamp"
        )

        if isinstance(
            timestamp,
            datetime,
        ):
            return (
                "#TALA18_15MIN_"
                f"{timestamp:%m%d%H%M}"
            )

    return (
        "#TALA18_15MIN_"
        f"{datetime.now():%m%d%H%M}"
    )


# ============================================================
# HEADER
# ============================================================

def _signal_header(
    signal: str,
) -> str:
    """
    هدر حرفه‌ای پیام.
    """

    if _is_buy_signal(signal):
        title = "🟢 سیگنال خرید طلا"

    elif _is_sell_signal(signal):
        title = "🔴 سیگنال فروش طلا"

    else:
        title = "🟡 وضعیت بازار طلا"

    return (
        "UnqGold | Tala 18\n"
        "UniqeApps\n"
        "UNIQE\n\n"
        f"{title}"
    )


# ============================================================
# MAIN FORMATTER
# ============================================================

def format_signal_message(
    analysis: Dict[str, Any],
) -> str:
    """
    ساخت پیام نهایی سیگنال.

    این تابع:
    - هیچ candle از DB نمی‌خواند.
    - فقط از _LIVE_CANDLES استفاده می‌کند.
    - قیمت‌ها را تومان نمایش می‌دهد.
    - احتمال‌ها را فقط از داده واقعی محاسبه می‌کند.
    """

    if not isinstance(
        analysis,
        dict,
    ):
        return (
            "❌ اطلاعات تحلیل معتبر نیست."
        )

    # --------------------------------------------------------
    # Live 15m candles
    # --------------------------------------------------------

    candles = _normalize_candles(
        get_live_candles("15m")
    )

    # --------------------------------------------------------
    # اگر به هر دلیل live candles هنوز
    # وارد حافظه نشده باشند، از داده‌ای که
    # خود analysis احتمالاً حمل می‌کند
    # استفاده می‌کنیم.
    #
    # این fallback هم DB نیست.
    # --------------------------------------------------------

    if not candles:

        analysis_candles = (
            analysis.get(
                "candles"
            )
        )

        if (
            isinstance(
                analysis_candles,
                list,
            )
            and analysis_candles
        ):
            candles = _normalize_candles(
                analysis_candles
            )

    # --------------------------------------------------------
    # Signal
    # --------------------------------------------------------

    signal = _extract_signal(
        analysis
    )

    # --------------------------------------------------------
    # Trade levels
    # --------------------------------------------------------

    levels = _calculate_trade_levels(
        analysis=analysis,
        candles=candles,
    )

    entry = levels.get(
        "entry"
    )

    stop = levels.get(
        "stop"
    )

    targets = levels.get(
        "targets",
        [],
    )

    atr = levels.get(
        "atr"
    )

    # --------------------------------------------------------
    # HOLD
    # --------------------------------------------------------

    if (
        not _is_buy_signal(signal)
        and not _is_sell_signal(signal)
    ):
        current_price = entry

        signal_id = _build_signal_id(
            candles
        )

        return (
            "UnqGold | Tala 18\n"
            "UniqeApps\n"
            "UNIQE\n\n"
            "🟡 وضعیت بازار طلا\n\n"
            f"📍 قیمت فعلی: "
            f"{_format_price(current_price)} تومان\n\n"
            "سیگنال معاملاتی قطعی "
            "وجود ندارد.\n\n"
            f"🆔 شناسه: {signal_id}"
        )

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    lines: List[str] = [
        _signal_header(signal),
        "",
        f"📍 ورود: "
        f"{_format_price(entry)}",
        f"🛑 حد ضرر: "
        f"{_format_price(stop)}",
        "",
    ]

    # --------------------------------------------------------
    # Targets
    # --------------------------------------------------------

    for index, target in enumerate(
        targets,
        start=1,
    ):
        lines.append(
            f"🎯 هدف {index}: "
            f"{_format_price(target)}"
        )

    # --------------------------------------------------------
    # Probabilities
    # --------------------------------------------------------

    lines.extend(
        [
            "",
            "📊 درصد احتمال برخورد اهداف "
            "بر اساس گذشته",
            "",
        ]
    )

    probabilities = (
        _calculate_target_probabilities(
            candles=candles,
            atr=atr,
            direction=signal,
        )
    )

    for index in range(
        len(TARGET_ATR_MULTIPLIERS)
    ):

        probability = (
            probabilities[index]
            if index < len(probabilities)
            else None
        )

        lines.append(
            f"هدف {index + 1} — "
            f"{_format_probability(probability)}"
        )

    # --------------------------------------------------------
    # Data quality information
    # --------------------------------------------------------

    if len(candles) < (
        MIN_HISTORY_SAMPLES
        + LOOKAHEAD_CANDLES
    ):
        lines.extend(
            [
                "",
                "ℹ️ توجه: "
                "داده تاریخی کافی برای "
                "محاسبه آماری احتمال اهداف "
                "در دسترس نیست.",
            ]
        )

    # --------------------------------------------------------
    # Signal ID
    # --------------------------------------------------------

    signal_id = _build_signal_id(
        candles
    )

    lines.extend(
        [
            "",
            f"🆔 شناسه: {signal_id}",
        ]
    )

    return "\n".join(lines)


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def format_analysis_summary(
    analysis: Dict[str, Any],
) -> str:
    """
    سازگاری با کدهای قدیمی پروژه.

    کد قدیمی اگر هنوز این تابع را صدا بزند،
    همان خروجی جدید را دریافت می‌کند.
    """

    return format_signal_message(
        analysis
    )
