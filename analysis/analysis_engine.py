# analysis/analysis_engine.py

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from database import (
    get_market_history,
    save_analysis,
)

from analysis.live_analysis_adapter import (
    get_live_analysis_candles,
)


# ============================================================
# CONFIG
# ============================================================

MIN_RELIABLE_5M_CANDLES = 25

TIMEFRAME_MIN_CANDLES = {
    "5m": 1,
    "15m": 1,
    "1h": 1,
}

RELIABLE_TIMEFRAME_CANDLES = {
    "5m": 25,
    "15m": 25,
    "1h": 25,
}

EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 21
EMA_MAJOR_PERIOD = 200

RSI_PERIOD = 14
ATR_PERIOD = 14

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

PRICE_DECIMALS = 0


# ============================================================
# BASIC HELPERS
# ============================================================

def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None

        number = float(value)

        if not math.isfinite(number):
            return None

        return number

    except (TypeError, ValueError):
        return None


def _normalize_candle(candle: Any) -> dict[str, Any] | None:
    if not isinstance(candle, dict):
        return None

    timestamp = (
        candle.get("timestamp")
        or candle.get("time")
        or candle.get("datetime")
        or candle.get("date")
    )

    open_price = _safe_float(
        candle.get("open")
    )

    high_price = _safe_float(
        candle.get("high")
    )

    low_price = _safe_float(
        candle.get("low")
    )

    close_price = _safe_float(
        candle.get("close")
    )

    if close_price is None:
        return None

    if open_price is None:
        open_price = close_price

    if high_price is None:
        high_price = max(
            open_price,
            close_price,
        )

    if low_price is None:
        low_price = min(
            open_price,
            close_price,
        )

    return {
        "timestamp": timestamp,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
    }


def normalize_candles(
    candles: Any,
) -> list[dict[str, Any]]:

    if not isinstance(candles, list):
        return []

    normalized = []

    for candle in candles:

        item = _normalize_candle(candle)

        if item is not None:
            normalized.append(item)

    normalized.sort(
        key=lambda item: str(
            item.get("timestamp", "")
        )
    )

    return normalized


# ============================================================
# LIVE CANDLES
# ============================================================

def fetch_live_candles(
    timeframe: str,
) -> list[dict[str, Any]]:

    try:

        live = get_live_analysis_candles()

        if not isinstance(live, dict):
            return []

        candles = live.get(
            timeframe,
            [],
        )

        return normalize_candles(
            candles
        )

    except Exception as exc:

        print(
            f"⚠️ LIVE CANDLES ERROR "
            f"[{timeframe}]: {exc!r}"
        )

        return []


def fetch_candles(
    timeframe: str,
) -> list[dict[str, Any]]:

    """
    تمام تحلیل‌ها فقط از Live Analysis Adapter
    دریافت می‌شوند.

    داده legacy از candle_engine عمداً استفاده نمی‌شود.
    """

    candles = fetch_live_candles(
        timeframe
    )

    print(
        f"📡 LIVE {timeframe.upper()} CANDLES:",
        len(candles),
    )

    return candles


# ============================================================
# DATA RELIABILITY
# ============================================================

def get_reliability_status(
    timeframe: str,
    candle_count: int,
) -> dict[str, Any]:

    reliable_after = RELIABLE_TIMEFRAME_CANDLES.get(
        timeframe,
        MIN_RELIABLE_5M_CANDLES,
    )

    if candle_count <= 0:

        return {
            "status": "NO_DATA",
            "label": "بدون داده",
            "reliable": False,
            "confidence": 0,
            "candle_count": 0,
            "required_for_reliable": reliable_after,
        }

    if candle_count < reliable_after:

        # از اولین کندل تحلیل فعال است.
        # فقط اعتبار آن پایین‌تر است.

        confidence = int(
            min(
                95,
                max(
                    5,
                    (
                        candle_count
                        / reliable_after
                    ) * 70,
                ),
            )
        )

        return {
            "status": "UNRELIABLE",
            "label": "غیرقابل اعتماد",
            "reliable": False,
            "confidence": confidence,
            "candle_count": candle_count,
            "required_for_reliable": reliable_after,
        }

    return {
        "status": "RELIABLE",
        "label": "قابل اعتماد",
        "reliable": True,
        "confidence": 70,
        "candle_count": candle_count,
        "required_for_reliable": reliable_after,
    }


# ============================================================
# PRICE DATA
# ============================================================

def get_closes(
    candles: list[dict[str, Any]],
) -> list[float]:

    values = []

    for candle in candles:

        close = _safe_float(
            candle.get("close")
        )

        if close is not None:
            values.append(close)

    return values


def get_highs(
    candles: list[dict[str, Any]],
) -> list[float]:

    values = []

    for candle in candles:

        high = _safe_float(
            candle.get("high")
        )

        if high is not None:
            values.append(high)

    return values


def get_lows(
    candles: list[dict[str, Any]],
) -> list[float]:

    values = []

    for candle in candles:

        low = _safe_float(
            candle.get("low")
        )

        if low is not None:
            values.append(low)

    return values


# ============================================================
# EMA
# ============================================================

def calculate_ema(
    values: list[float],
    period: int,
) -> float | None:

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    ema = sum(
        values[:period]
    ) / period

    for price in values[period:]:

        ema = (
            (price - ema) * multiplier
        ) + ema

    return ema


# ============================================================
# RSI
# ============================================================

def calculate_rsi(
    values: list[float],
    period: int = RSI_PERIOD,
) -> float | None:

    if len(values) < period + 1:
        return None

    changes = []

    for index in range(1, len(values)):

        changes.append(
            values[index]
            - values[index - 1]
        )

    gains = [
        max(change, 0)
        for change in changes
    ]

    losses = [
        max(-change, 0)
        for change in changes
    ]

    avg_gain = (
        sum(gains[:period])
        / period
    )

    avg_loss = (
        sum(losses[:period])
        / period
    )

    for index in range(
        period,
        len(changes),
    ):

        avg_gain = (
            (
                avg_gain * (period - 1)
            )
            + gains[index]
        ) / period

        avg_loss = (
            (
                avg_loss * (period - 1)
            )
            + losses[index]
        ) / period

    if avg_loss == 0:

        if avg_gain == 0:
            return 50.0

        return 100.0

    relative_strength = (
        avg_gain / avg_loss
    )

    return (
        100
        - (
            100
            / (
                1
                + relative_strength
            )
        )
    )


# ============================================================
# MACD
# ============================================================

def calculate_macd(
    values: list[float],
) -> dict[str, float | None]:

    minimum = (
        MACD_SLOW
        + MACD_SIGNAL
        - 1
    )

    if len(values) < minimum:

        return {
            "macd": None,
            "signal": None,
            "histogram": None,
        }

    macd_values = []

    for index in range(
        MACD_SLOW - 1,
        len(values),
    ):

        subset = values[
            : index + 1
        ]

        fast_ema = calculate_ema(
            subset,
            MACD_FAST,
        )

        slow_ema = calculate_ema(
            subset,
            MACD_SLOW,
        )

        if (
            fast_ema is None
            or slow_ema is None
        ):
            continue

        macd_values.append(
            fast_ema - slow_ema
        )

    if len(macd_values) < MACD_SIGNAL:
        return {
            "macd": None,
            "signal": None,
            "histogram": None,
        }

    signal = calculate_ema(
        macd_values,
        MACD_SIGNAL,
    )

    macd_value = macd_values[-1]

    if signal is None:
        return {
            "macd": macd_value,
            "signal": None,
            "histogram": None,
        }

    return {
        "macd": macd_value,
        "signal": signal,
        "histogram": (
            macd_value - signal
        ),
    }


# ============================================================
# ATR
# ============================================================

def calculate_atr(
    candles: list[dict[str, Any]],
    period: int = ATR_PERIOD,
) -> float | None:

    if len(candles) < period + 1:
        return None

    true_ranges = []

    for index in range(
        1,
        len(candles),
    ):

        current = candles[index]
        previous = candles[index - 1]

        high = current["high"]
        low = current["low"]
        previous_close = previous["close"]

        true_range = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close),
        )

        true_ranges.append(
            true_range
        )

    if len(true_ranges) < period:
        return None

    return (
        sum(
            true_ranges[-period:]
        )
        / period
    )


# ============================================================
# PRICE CHANGE
# ============================================================

def calculate_price_change(
    values: list[float],
    periods: int = 5,
) -> float | None:

    if len(values) <= periods:
        return None

    old_price = values[
        -periods - 1
    ]

    new_price = values[-1]

    if old_price == 0:
        return None

    return (
        (
            new_price
            - old_price
        )
        / old_price
    ) * 100


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def calculate_structure_state(
    candles: list[dict[str, Any]],
) -> dict[str, Any]:

    if not candles:

        return {
            "support": None,
            "resistance": None,
            "trend": "UNKNOWN",
            "breakout": "NONE",
        }

    closes = get_closes(candles)
    highs = get_highs(candles)
    lows = get_lows(candles)

    if not closes:

        return {
            "support": None,
            "resistance": None,
            "trend": "UNKNOWN",
            "breakout": "NONE",
        }

    latest = closes[-1]

    support = None
    resistance = None

    if len(lows) >= 2:
        support = min(lows[:-1])

    if len(highs) >= 2:
        resistance = max(highs[:-1])

    trend = "NEUTRAL"

    if len(closes) >= 3:

        recent = closes[-3:]

        if (
            recent[-1] > recent[-2]
            > recent[-3]
        ):
            trend = "BULLISH"

        elif (
            recent[-1] < recent[-2]
            < recent[-3]
        ):
            trend = "BEARISH"

    breakout = "NONE"

    if (
        resistance is not None
        and latest > resistance
    ):
        breakout = "BREAKOUT_UP"

    elif (
        support is not None
        and latest < support
    ):
        breakout = "BREAKOUT_DOWN"

    return {
        "support": support,
        "resistance": resistance,
        "trend": trend,
        "breakout": breakout,
    }


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(
    timeframe: str,
    candles: list[dict[str, Any]],
) -> dict[str, Any]:

    candle_count = len(candles)

    reliability = get_reliability_status(
        timeframe,
        candle_count,
    )

    if candle_count == 0:

        return {
            "timeframe": timeframe,
            "available": False,
            "candles": 0,
            "reliability": reliability,
            "indicators": {},
            "structure": {},
        }

    closes = get_closes(candles)

    if not closes:

        return {
            "timeframe": timeframe,
            "available": False,
            "candles": candle_count,
            "reliability": reliability,
            "indicators": {},
            "structure": {},
        }

    ema_fast = calculate_ema(
        closes,
        EMA_FAST_PERIOD,
    )

    ema_slow = calculate_ema(
        closes,
        EMA_SLOW_PERIOD,
    )

    ema_major = calculate_ema(
        closes,
        EMA_MAJOR_PERIOD,
    )

    rsi = calculate_rsi(
        closes,
        RSI_PERIOD,
    )

    macd = calculate_macd(
        closes,
    )

    atr = calculate_atr(
        candles,
        ATR_PERIOD,
    )

    price_change = calculate_price_change(
        closes,
        5,
    )

    structure = calculate_structure_state(
        candles,
    )

    trend = structure.get(
        "trend",
        "UNKNOWN",
    )

    # EMA trend
    if (
        ema_fast is not None
        and ema_slow is not None
    ):

        if ema_fast > ema_slow:

            ema_trend = "BULLISH"

        elif ema_fast < ema_slow:

            ema_trend = "BEARISH"

        else:

            ema_trend = "NEUTRAL"

    else:

        ema_trend = "UNAVAILABLE"

    return {
        "timeframe": timeframe,
        "available": True,
        "candles": candle_count,
        "latest_price": closes[-1],
        "reliability": reliability,

        "indicators": {
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "ema_major": ema_major,
            "ema_trend": ema_trend,
            "rsi": rsi,
            "macd": macd,
            "atr": atr,
            "price_change_5": price_change,
        },

        "structure": structure,
    }


# ============================================================
# MULTI TIMEFRAME
# ============================================================

def analyze_multi_timeframe() -> dict[str, Any]:

    results = {}

    for timeframe in (
        "5m",
        "15m",
        "1h",
    ):

        candles = fetch_candles(
            timeframe
        )

        results[timeframe] = (
            analyze_timeframe(
                timeframe,
                candles,
            )
        )

    return results


# ============================================================
# SIGNAL ENGINE
# ============================================================

def calculate_signal(
    analysis_5m: dict[str, Any],
    mtf: dict[str, Any],
) -> dict[str, Any]:

    if not analysis_5m.get(
        "available",
        False,
    ):

        return {
            "signal": "WAIT",
            "score": 0,
            "reason": "NO_DATA",
        }

    reliability = analysis_5m.get(
        "reliability",
        {},
    )

    candles = reliability.get(
        "candle_count",
        0,
    )

    indicators = analysis_5m.get(
        "indicators",
        {},
    )

    structure = analysis_5m.get(
        "structure",
        {},
    )

    score = 0

    reasons = []

    # --------------------------------------------------------
    # EMA
    # --------------------------------------------------------

    ema_trend = indicators.get(
        "ema_trend"
    )

    if ema_trend == "BULLISH":

        score += 1
        reasons.append(
            "EMA bullish"
        )

    elif ema_trend == "BEARISH":

        score -= 1
        reasons.append(
            "EMA bearish"
        )

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = indicators.get(
        "rsi"
    )

    if rsi is not None:

        if rsi >= 70:

            score -= 1
            reasons.append(
                "RSI overbought"
            )

        elif rsi <= 30:

            score += 1
            reasons.append(
                "RSI oversold"
            )

        elif rsi > 50:

            score += 1
            reasons.append(
                "RSI bullish"
            )

        elif rsi < 50:

            score -= 1
            reasons.append(
                "RSI bearish"
            )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    macd = indicators.get(
        "macd",
        {},
    )

    histogram = macd.get(
        "histogram"
    )

    if histogram is not None:

        if histogram > 0:

            score += 1
            reasons.append(
                "MACD bullish"
            )

        elif histogram < 0:

            score -= 1
            reasons.append(
                "MACD bearish"
            )

    # --------------------------------------------------------
    # STRUCTURE
    # --------------------------------------------------------

    trend = structure.get(
        "trend"
    )

    if trend == "BULLISH":

        score += 1
        reasons.append(
            "price structure bullish"
        )

    elif trend == "BEARISH":

        score -= 1
        reasons.append(
            "price structure bearish"
        )

    breakout = structure.get(
        "breakout"
    )

    if breakout == "BREAKOUT_UP":

        score += 2
        reasons.append(
            "resistance breakout"
        )

    elif breakout == "BREAKOUT_DOWN":

        score -= 2
        reasons.append(
            "support breakdown"
        )

    # --------------------------------------------------------
    # MULTI TIMEFRAME CONFIRMATION
    # --------------------------------------------------------

    mtf_bullish = 0
    mtf_bearish = 0
    mtf_available = 0

    for timeframe in (
        "15m",
        "1h",
    ):

        item = mtf.get(
            timeframe,
            {},
        )

        if not item.get(
            "available",
            False,
        ):
            continue

        mtf_available += 1

        item_structure = item.get(
            "structure",
            {},
        )

        item_trend = item_structure.get(
            "trend"
        )

        if item_trend == "BULLISH":
            mtf_bullish += 1

        elif item_trend == "BEARISH":
            mtf_bearish += 1

    if mtf_bullish > mtf_bearish:

        score += 1
        reasons.append(
            "MTF bullish"
        )

    elif mtf_bearish > mtf_bullish:

        score -= 1
        reasons.append(
            "MTF bearish"
        )

    # --------------------------------------------------------
    # EARLY-STAGE PROTECTION
    # --------------------------------------------------------

    # قبل از 25 کندل تحلیل انجام می‌شود،
    # اما اجازه سیگنال قوی داده نمی‌شود.

    if candles < MIN_RELIABLE_5M_CANDLES:

        return {
            "signal": "WAIT",
            "score": score,
            "reasons": reasons,
            "reason": (
                "INSUFFICIENT_HISTORY_FOR_RELIABLE_SIGNAL"
            ),
            "reliable": False,
            "mtf_available": mtf_available,
        }

    # --------------------------------------------------------
    # FINAL SIGNAL
    # --------------------------------------------------------

    if score >= 3:

        signal = "BUY"

    elif score <= -3:

        signal = "SELL"

    else:

        signal = "HOLD"

    return {
        "signal": signal,
        "score": score,
        "reasons": reasons,
        "reason": "NORMAL",
        "reliable": True,
        "mtf_available": mtf_available,
    }


# ============================================================
# MARKET HISTORY
# ============================================================

def get_latest_market_data() -> dict[str, Any]:

    try:

        history = get_market_history()

        if not history:
            return {}

        if isinstance(
            history,
            dict,
        ):
            return history

        if isinstance(
            history,
            list,
        ):

            if not history:
                return {}

            latest = history[-1]

            if isinstance(
                latest,
                dict,
            ):
                return latest

        return {}

    except Exception as exc:

        print(
            "⚠️ MARKET HISTORY ERROR:",
            repr(exc),
        )

        return {}


# ============================================================
# FAIR VALUE
# ============================================================

def calculate_fair_value(
    world_gold_usd: float | None,
    usd_mid_toman: float | None,
) -> float | None:

    if (
        world_gold_usd is None
        or usd_mid_toman is None
    ):
        return None

    try:

        ounce_to_gram = 31.1034768

        purity_18k = 0.75

        return (
            world_gold_usd
            * usd_mid_toman
            / ounce_to_gram
            * purity_18k
        )

    except Exception:

        return None


# ============================================================
# TRADE LEVELS
# ============================================================

def calculate_trade_levels(
    price: float,
    structure: dict[str, Any],
    atr: float | None,
    signal: str,
) -> dict[str, Any]:

    support = structure.get(
        "support"
    )

    resistance = structure.get(
        "resistance"
    )

    if price <= 0:

        return {
            "stop_loss": None,
            "target_1": None,
            "target_2": None,
        }

    volatility = atr

    if volatility is None or volatility <= 0:

        volatility = price * 0.003

    if signal == "BUY":

        if support is not None:
            stop_loss = support
        else:
            stop_loss = (
                price - volatility
            )

        risk = max(
            price - stop_loss,
            volatility * 0.5,
        )

        target_1 = (
            price + risk
        )

        target_2 = (
            price + risk * 2
        )

    elif signal == "SELL":

        if resistance is not None:
            stop_loss = resistance
        else:
            stop_loss = (
                price + volatility
            )

        risk = max(
            stop_loss - price,
            volatility * 0.5,
        )

        target_1 = (
            price - risk
        )

        target_2 = (
            price - risk * 2
        )

    else:

        stop_loss = None
        target_1 = None
        target_2 = None

    return {
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
    }


# ============================================================
# MAIN ANALYSIS
# ============================================================

def run_analysis() -> dict[str, Any]:

    print(
        "Professional Analysis: starting..."
    )

    # --------------------------------------------------------
    # LIVE MULTI TIMEFRAME
    # --------------------------------------------------------

    mtf = analyze_multi_timeframe()

    analysis_5m = mtf.get(
        "5m",
        {},
    )

    candles_5m = analysis_5m.get(
        "candles",
        0,
    )

    reliability = analysis_5m.get(
        "reliability",
        {},
    )

    # --------------------------------------------------------
    # CURRENT PRICE
    # --------------------------------------------------------

    latest_price = (
        analysis_5m.get(
            "latest_price"
        )
    )

    market_data = (
        get_latest_market_data()
    )

    # قیمت واقعی تحلیل باید از Live 5m بیاید.
    # market history فقط برای داده‌های جانبی استفاده می‌شود.

    price = _safe_float(
        latest_price
    )

    if price is None:

        price = _safe_float(
            market_data.get(
                "gold_18k_toman"
            )
        )

    if price is None:

        price = _safe_float(
            market_data.get(
                "gold_18k"
            )
        )

    # --------------------------------------------------------
    # MARKET DATA
    # --------------------------------------------------------

    world_gold_usd = _safe_float(
        market_data.get(
            "world_gold_usd"
        )
    )

    usd_mid_toman = _safe_float(
        market_data.get(
            "usd_mid_toman"
        )
    )

    servix_price = _safe_float(
        market_data.get(
            "servix_18k_toman"
        )
    )

    fair_value = calculate_fair_value(
        world_gold_usd,
        usd_mid_toman,
    )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    signal_data = calculate_signal(
        analysis_5m,
        mtf,
    )

    signal = signal_data.get(
        "signal",
        "WAIT",
    )

    # --------------------------------------------------------
    # TRADE LEVELS
    # --------------------------------------------------------

    indicators = analysis_5m.get(
        "indicators",
        {},
    )

    structure = analysis_5m.get(
        "structure",
        {},
    )

    atr = indicators.get(
        "atr"
    )

    trade_levels = {}

    if price is not None:

        trade_levels = (
            calculate_trade_levels(
                price,
                structure,
                atr,
                signal,
            )
        )

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    reliable = reliability.get(
        "reliable",
        False,
    )

    if reliable:

        reliability_message = (
            "قابل اعتماد"
        )

    else:

        reliability_message = (
            "غیرقابل اعتماد"
        )

    # --------------------------------------------------------
    # ANALYSIS DATA
    # --------------------------------------------------------

    analysis_data = {

        "timestamp": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),

        "price_toman": price,

        "world_gold_usd": (
            world_gold_usd
        ),

        "usd_mid_toman": (
            usd_mid_toman
        ),

        "servix_18k_toman": (
            servix_price
        ),

        "fair_value_toman": (
            fair_value
        ),

        "candles": {
            "5m": candles_5m,
            "15m": mtf.get(
                "15m",
                {},
            ).get(
                "candles",
                0,
            ),
            "1h": mtf.get(
                "1h",
                {},
            ).get(
                "candles",
                0,
            ),
        },

        "reliability": {

            "status": reliability.get(
                "status"
            ),

            "label": reliability_message,

            "reliable": reliable,

            "confidence": reliability.get(
                "confidence",
                0,
            ),

            "candles_5m": candles_5m,

            "minimum_for_reliable": (
                MIN_RELIABLE_5M_CANDLES
            ),
        },

        "timeframes": mtf,

        "signal": signal_data,

        "trade_levels": trade_levels,

        "data_quality": {

            "analysis_started": (
                candles_5m >= 1
            ),

            "reliable": reliable,

            "5m_history_sufficient": (
                candles_5m
                >= MIN_RELIABLE_5M_CANDLES
            ),

            "mtf_15m_available": (
                mtf.get(
                    "15m",
                    {},
                ).get(
                    "available",
                    False,
                )
            ),

            "mtf_1h_available": (
                mtf.get(
                    "1h",
                    {},
                ).get(
                    "available",
                    False,
                )
            ),
        },
    }

    # --------------------------------------------------------
    # LOGGING
    # --------------------------------------------------------

    print(
        "📊 5M CANDLES:",
        candles_5m,
    )

    print(
        "📊 ANALYSIS STATUS:",
        reliability_message,
    )

    print(
        "📊 ANALYSIS CONFIDENCE:",
        reliability.get(
            "confidence",
            0,
        ),
        "%",
    )

    print(
        "🎯 SIGNAL:",
        signal,
    )

    if price is not None:

        print(
            "💰 LIVE PRICE:",
            f"{price:,.0f}",
            "TOMAN",
        )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    try:

        save_analysis(
            analysis_data
        )

    except TypeError:

        try:

            save_analysis(
                analysis_data
            )

        except Exception as exc:

            print(
                "⚠️ SAVE ANALYSIS ERROR:",
                repr(exc),
            )

    except Exception as exc:

        print(
            "⚠️ SAVE ANALYSIS ERROR:",
            repr(exc),
        )

    return analysis_data


# ============================================================
# SUMMARY FORMAT
# ============================================================

def format_analysis_summary(
    analysis: dict[str, Any],
) -> str:

    price = analysis.get(
        "price_toman"
    )

    reliability = analysis.get(
        "reliability",
        {},
    )

    signal_data = analysis.get(
        "signal",
        {},
    )

    signal = signal_data.get(
        "signal",
        "WAIT",
    )

    candles = reliability.get(
        "candles_5m",
        0,
    )

    confidence = reliability.get(
        "confidence",
        0,
    )

    status = reliability.get(
        "label",
        "غیرقابل اعتماد",
    )

    lines = []

    lines.append(
        "🤖 Professional Gold Analysis"
    )

    lines.append("")

    if price is not None:

        lines.append(
            f"💰 قیمت: {price:,.0f} تومان"
        )

    lines.append(
        f"🕯️ کندل 5 دقیقه‌ای: "
        f"{candles}"
    )

    lines.append(
        f"📊 وضعیت تحلیل: {status}"
    )

    lines.append(
        f"📈 میزان اعتماد: {confidence}%"
    )

    lines.append("")

    if candles < MIN_RELIABLE_5M_CANDLES:

        remaining = (
            MIN_RELIABLE_5M_CANDLES
            - candles
        )

        lines.append(
            "⚠️ هشدار: "
            "این تحلیل هنوز قابل اعتماد نیست."
        )

        lines.append(
            f"⏳ {remaining} کندل 5 دقیقه‌ای "
            "تا رسیدن به حداقل اعتبار باقی مانده."
        )

    lines.append("")

    lines.append(
        f"🎯 نتیجه: {signal}"
    )

    if signal == "WAIT":

        lines.append(
            "⏸️ فعلاً از صدور سیگنال معاملاتی "
            "خودداری می‌شود."
        )

    return "\n".join(lines)
