import json
import math
from datetime import datetime, timezone

from database import (
    get_market_history,
    save_analysis,
)

from candle_engine import (
    get_recent_candles,
)


# ============================================================
# CONFIG
# ============================================================

SYMBOL = "GOLD_18K_TOMAN"

TROY_OUNCE_GRAMS = 31.1034768
GOLD_18K_PURITY = 0.75

EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 21

RSI_PERIOD = 14
ATR_PERIOD = 14
MOMENTUM_PERIOD = 10

SUPPORT_RESISTANCE_LOOKBACK = 20

MIN_CANDLES_FOR_ANALYSIS = 25

# Market score weights
WEIGHT_TREND = 25
WEIGHT_MOMENTUM = 15
WEIGHT_RSI = 15
WEIGHT_MACD = 15
WEIGHT_EMA_POSITION = 10
WEIGHT_FAIR_VALUE = 10
WEIGHT_STRUCTURE = 10


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value, default=None):

    try:

        if value is None:
            return default

        number = float(value)

        if not math.isfinite(number):
            return default

        return number

    except (TypeError, ValueError):

        return default


def clamp(value, minimum, maximum):

    value = safe_float(value)

    if value is None:
        return minimum

    return min(
        max(value, minimum),
        maximum
    )


def average(values):

    cleaned = []

    for value in values:

        number = safe_float(value)

        if number is not None:
            cleaned.append(number)

    if not cleaned:
        return None

    return sum(cleaned) / len(cleaned)


# ============================================================
# CANDLE HELPERS
# ============================================================

def candle_close(candle):

    if not candle:
        return None

    for key in (
        "close",
        "close_price",
    ):

        value = safe_float(
            candle.get(key)
        )

        if value is not None:
            return value

    return None


def candle_open(candle):

    if not candle:
        return None

    for key in (
        "open",
        "open_price",
    ):

        value = safe_float(
            candle.get(key)
        )

        if value is not None:
            return value

    return None


def candle_high(candle):

    if not candle:
        return None

    for key in (
        "high",
        "high_price",
    ):

        value = safe_float(
            candle.get(key)
        )

        if value is not None:
            return value

    return None


def candle_low(candle):

    if not candle:
        return None

    for key in (
        "low",
        "low_price",
    ):

        value = safe_float(
            candle.get(key)
        )

        if value is not None:
            return value

    return None


# ============================================================
# CLOSE SERIES
# ============================================================

def get_closes(candles):

    closes = []

    for candle in candles:

        close = candle_close(candle)

        if close is not None:
            closes.append(close)

    return closes


# ============================================================
# EMA
# ============================================================

def calculate_ema(values, period):

    cleaned = []

    for value in values:

        number = safe_float(value)

        if number is not None:
            cleaned.append(number)

    if len(cleaned) < period:
        return None

    sma = (
        sum(cleaned[:period])
        / period
    )

    multiplier = 2 / (period + 1)

    ema = sma

    for price in cleaned[period:]:

        ema = (
            (price - ema)
            * multiplier
        ) + ema

    return ema


# ============================================================
# RSI
# ============================================================

def calculate_rsi(values, period=14):

    cleaned = []

    for value in values:

        number = safe_float(value)

        if number is not None:
            cleaned.append(number)

    if len(cleaned) <= period:
        return None

    gains = []
    losses = []

    for index in range(
        1,
        len(cleaned)
    ):

        change = (
            cleaned[index]
            - cleaned[index - 1]
        )

        if change > 0:

            gains.append(change)
            losses.append(0)

        else:

            gains.append(0)
            losses.append(abs(change))

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
        len(gains)
    ):

        avg_gain = (
            (
                avg_gain
                * (period - 1)
            )
            + gains[index]
        ) / period

        avg_loss = (
            (
                avg_loss
                * (period - 1)
            )
            + losses[index]
        ) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    return 100 - (
        100 / (1 + rs)
    )


# ============================================================
# MACD
# ============================================================

def calculate_macd(values):

    if len(values) < 35:
        return None

    ema_fast_values = []

    for index in range(
        EMA_FAST_PERIOD,
        len(values) + 1
    ):

        value = calculate_ema(
            values[:index],
            EMA_FAST_PERIOD
        )

        if value is not None:
            ema_fast_values.append(value)

    ema_slow_values = []

    for index in range(
        EMA_SLOW_PERIOD,
        len(values) + 1
    ):

        value = calculate_ema(
            values[:index],
            EMA_SLOW_PERIOD
        )

        if value is not None:
            ema_slow_values.append(value)

    if not ema_fast_values or not ema_slow_values:
        return None

    # Align the two EMA series by their latest section.
    difference = (
        len(ema_fast_values)
        - len(ema_slow_values)
    )

    if difference > 0:
        ema_fast_values = (
            ema_fast_values[difference:]
        )

    elif difference < 0:
        ema_slow_values = (
            ema_slow_values[-difference:]
        )

    macd_values = []

    for fast, slow in zip(
        ema_fast_values,
        ema_slow_values
    ):

        macd_values.append(
            fast - slow
        )

    if len(macd_values) < 9:
        return None

    macd = macd_values[-1]

    signal = calculate_ema(
        macd_values,
        9
    )

    if signal is None:
        return None

    histogram = (
        macd - signal
    )

    return {
        "macd": macd,
        "signal": signal,
        "histogram": histogram,
    }


# ============================================================
# ATR
# ============================================================

def calculate_atr(candles, period=14):

    if len(candles) < period:
        return None

    true_ranges = []

    previous_close = None

    for candle in candles:

        high = candle_high(candle)
        low = candle_low(candle)
        close = candle_close(candle)

        if (
            high is None
            or low is None
        ):
            continue

        if previous_close is None:

            true_range = (
                high - low
            )

        else:

            true_range = max(
                high - low,
                abs(
                    high
                    - previous_close
                ),
                abs(
                    low
                    - previous_close
                ),
            )

        if true_range >= 0:

            true_ranges.append(
                true_range
            )

        if close is not None:
            previous_close = close

    if len(true_ranges) < period:
        return None

    return average(
        true_ranges[-period:]
    )


# ============================================================
# MOMENTUM
# ============================================================

def calculate_momentum(
    values,
    period=MOMENTUM_PERIOD
):

    if len(values) <= period:
        return None

    current = safe_float(
        values[-1]
    )

    previous = safe_float(
        values[-1 - period]
    )

    if (
        current is None
        or previous is None
        or previous == 0
    ):
        return None

    return (
        (
            current
            - previous
        )
        / previous
    ) * 100


# ============================================================
# PRICE CHANGE
# ============================================================

def calculate_price_change(
    values,
    period
):

    if len(values) <= period:
        return None

    current = safe_float(
        values[-1]
    )

    previous = safe_float(
        values[-1 - period]
    )

    if (
        current is None
        or previous is None
        or previous == 0
    ):
        return None

    return (
        (
            current
            - previous
        )
        / previous
    ) * 100


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def calculate_support_resistance(
    candles,
    lookback=20
):

    recent = candles[-lookback:]

    highs = []
    lows = []

    for candle in recent:

        high = candle_high(candle)
        low = candle_low(candle)

        if high is not None:
            highs.append(high)

        if low is not None:
            lows.append(low)

    if not highs or not lows:
        return None, None

    return (
        min(lows),
        max(highs),
    )


# ============================================================
# FAIR VALUE
# ============================================================

def calculate_fair_value(
    world_gold_usd,
    usd_mid_toman
):

    world_gold_usd = safe_float(
        world_gold_usd
    )

    usd_mid_toman = safe_float(
        usd_mid_toman
    )

    if (
        world_gold_usd is None
        or usd_mid_toman is None
    ):
        return None

    pure_gold_per_gram = (
        world_gold_usd
        * usd_mid_toman
        / TROY_OUNCE_GRAMS
    )

    gold_18k_per_gram = (
        pure_gold_per_gram
        * GOLD_18K_PURITY
    )

    return gold_18k_per_gram


# ============================================================
# FAIR VALUE DEVIATION
# ============================================================

def calculate_fair_value_deviation(
    price,
    fair_value
):

    if (
        price is None
        or fair_value is None
        or fair_value == 0
    ):
        return None

    return (
        (
            price
            - fair_value
        )
        / fair_value
    ) * 100


# ============================================================
# SOURCE SPREAD
# ============================================================

def calculate_source_spread(
    market_price,
    servix_price
):

    market_price = safe_float(
        market_price
    )

    servix_price = safe_float(
        servix_price
    )

    if (
        market_price is None
        or servix_price is None
        or market_price == 0
    ):
        return None

    return (
        (
            market_price
            - servix_price
        )
        / market_price
    ) * 100


# ============================================================
# EMA POSITION
# ============================================================

def calculate_ema_position(
    price,
    ema_fast,
    ema_slow
):

    if (
        price is None
        or ema_fast is None
        or ema_slow is None
    ):
        return {
            "direction": "unknown",
            "score": 0,
        }

    score = 0

    if price > ema_fast:
        score += 1

    elif price < ema_fast:
        score -= 1

    if price > ema_slow:
        score += 1

    elif price < ema_slow:
        score -= 1

    if score >= 2:

        direction = "bullish"

    elif score <= -2:

        direction = "bearish"

    else:

        direction = "neutral"

    return {
        "direction": direction,
        "score": score,
    }


# ============================================================
# TREND STRENGTH
# ============================================================

def calculate_trend_strength(
    ema_fast,
    ema_slow,
    price,
    momentum,
    rsi
):

    components = []

    if (
        ema_fast is not None
        and ema_slow is not None
        and ema_slow != 0
    ):

        ema_gap = (
            (
                ema_fast
                - ema_slow
            )
            / ema_slow
        ) * 100

        components.append(
            min(abs(ema_gap) * 20, 100)
        )

    if momentum is not None:

        components.append(
            min(abs(momentum) * 10, 100)
        )

    if rsi is not None:

        rsi_strength = abs(
            rsi - 50
        ) * 2

        components.append(
            min(rsi_strength, 100)
        )

    if not components:
        return 0.0

    return round(
        average(components),
        2
    )


# ============================================================
# MARKET REGIME
# ============================================================

def calculate_market_regime(
    trend,
    trend_strength,
    atr,
    price,
    momentum,
    rsi
):

    if price is None:
        return "UNKNOWN"

    volatility_percent = None

    if (
        atr is not None
        and price > 0
    ):

        volatility_percent = (
            atr / price
        ) * 100

    strong_trend = (
        trend_strength is not None
        and trend_strength >= 55
    )

    strong_momentum = (
        momentum is not None
        and abs(momentum) >= 0.4
    )

    high_volatility = (
        volatility_percent is not None
        and volatility_percent >= 0.8
    )

    if trend == "صعودی" and (
        strong_trend
        or strong_momentum
    ):

        if high_volatility:
            return "BULLISH_VOLATILE"

        return "BULLISH_TREND"

    if trend == "نزولی" and (
        strong_trend
        or strong_momentum
    ):

        if high_volatility:
            return "BEARISH_VOLATILE"

        return "BEARISH_TREND"

    if high_volatility:
        return "HIGH_VOLATILITY"

    if (
        rsi is not None
        and 45 <= rsi <= 55
    ):

        return "RANGE"

    return "TRANSITION"


# ============================================================
# INDICATOR DIRECTIONS
# ============================================================

def indicator_direction(
    rsi,
    macd,
    momentum,
    ema_position,
    fair_value_deviation,
    price,
    support,
    resistance
):

    directions = {
        "rsi": 0,
        "macd": 0,
        "momentum": 0,
        "ema": 0,
        "fair_value": 0,
        "structure": 0,
    }

    # RSI
    if rsi is not None:

        if 50 <= rsi <= 70:
            directions["rsi"] = 1

        elif 30 <= rsi < 50:
            directions["rsi"] = -1

        elif rsi > 70:
            directions["rsi"] = -1

        elif rsi < 30:
            directions["rsi"] = 1

    # MACD
    if macd:

        histogram = safe_float(
            macd.get("histogram")
        )

        if histogram is not None:

            if histogram > 0:
                directions["macd"] = 1

            elif histogram < 0:
                directions["macd"] = -1

    # Momentum
    if momentum is not None:

        if momentum > 0:
            directions["momentum"] = 1

        elif momentum < 0:
            directions["momentum"] = -1

    # EMA
    if ema_position:

        directions["ema"] = (
            1
            if ema_position.get("score", 0) > 0
            else -1
            if ema_position.get("score", 0) < 0
            else 0
        )

    # Fair value
    if fair_value_deviation is not None:

        if fair_value_deviation < -2:
            directions["fair_value"] = 1

        elif fair_value_deviation > 2:
            directions["fair_value"] = -1

    # Structure
    if (
        resistance is not None
        and price is not None
        and price > resistance
    ):

        directions["structure"] = 1

    elif (
        support is not None
        and price is not None
        and price < support
    ):

        directions["structure"] = -1

    return directions


# ============================================================
# MARKET SCORE
# ============================================================

def calculate_market_score(
    trend,
    trend_strength,
    rsi,
    macd,
    momentum,
    ema_position,
    fair_value_deviation,
    price,
    support,
    resistance
):

    directions = indicator_direction(
        rsi,
        macd,
        momentum,
        ema_position,
        fair_value_deviation,
        price,
        support,
        resistance,
    )

    bullish = 0.0
    bearish = 0.0

    # Trend
    if trend == "صعودی":

        bullish += (
            WEIGHT_TREND
            * max(
                trend_strength / 100,
                0.5
            )
        )

    elif trend == "نزولی":

        bearish += (
            WEIGHT_TREND
            * max(
                trend_strength / 100,
                0.5
            )
        )

    # Momentum
    if directions["momentum"] > 0:
        bullish += WEIGHT_MOMENTUM

    elif directions["momentum"] < 0:
        bearish += WEIGHT_MOMENTUM

    # RSI
    if directions["rsi"] > 0:
        bullish += WEIGHT_RSI

    elif directions["rsi"] < 0:
        bearish += WEIGHT_RSI

    # MACD
    if directions["macd"] > 0:
        bullish += WEIGHT_MACD

    elif directions["macd"] < 0:
        bearish += WEIGHT_MACD

    # EMA
    if directions["ema"] > 0:
        bullish += WEIGHT_EMA_POSITION

    elif directions["ema"] < 0:
        bearish += WEIGHT_EMA_POSITION

    # Fair value
    if directions["fair_value"] > 0:
        bullish += WEIGHT_FAIR_VALUE

    elif directions["fair_value"] < 0:
        bearish += WEIGHT_FAIR_VALUE

    # Structure
    if directions["structure"] > 0:
        bullish += WEIGHT_STRUCTURE

    elif directions["structure"] < 0:
        bearish += WEIGHT_STRUCTURE

    total = (
        bullish
        + bearish
    )

    if total <= 0:
        return {
            "score": 50.0,
            "bullish": 0.0,
            "bearish": 0.0,
            "bias": "NEUTRAL",
            "components": directions,
        }

    score = (
        50
        + (
            (
                bullish
                - bearish
            )
            / total
        )
        * 50
    )

    score = clamp(
        score,
        0,
        100
    )

    if score >= 65:
        bias = "BULLISH"

    elif score <= 35:
        bias = "BEARISH"

    else:
        bias = "NEUTRAL"

    return {
        "score": round(score, 2),
        "bullish": round(bullish, 2),
        "bearish": round(bearish, 2),
        "bias": bias,
        "components": directions,
    }


# ============================================================
# TREND
# ============================================================

def calculate_trend(
    price,
    ema_fast,
    ema_slow,
    momentum,
    rsi
):

    score = 0

    if (
        ema_fast is not None
        and ema_slow is not None
    ):

        if ema_fast > ema_slow:
            score += 2

        elif ema_fast < ema_slow:
            score -= 2

    if momentum is not None:

        if momentum > 0:
            score += 1

        elif momentum < 0:
            score -= 1

    if rsi is not None:

        if rsi >= 55:
            score += 1

        elif rsi <= 45:
            score -= 1

    if score >= 3:
        return "صعودی"

    if score <= -3:
        return "نزولی"

    return "خنثی"


# ============================================================
# SIGNAL
# ============================================================

def calculate_signal(
    market_score,
    trend,
    rsi,
    macd,
    fair_value_deviation,
    price,
    support,
    resistance
):

    score = 0.0

    # Market score
    if market_score is not None:

        score += (
            (
                market_score
                - 50
            )
            / 50
        ) * 4

    # Trend
    if trend == "صعودی":
        score += 2

    elif trend == "نزولی":
        score -= 2

    # RSI
    if rsi is not None:

        if 50 <= rsi <= 70:
            score += 1

        elif 30 <= rsi < 50:
            score -= 1

        elif rsi > 75:
            score -= 1

        elif rsi < 25:
            score += 1

    # MACD
    if macd:

        histogram = safe_float(
            macd.get("histogram")
        )

        if histogram is not None:

            if histogram > 0:
                score += 1

            elif histogram < 0:
                score -= 1

    # Fair value
    if fair_value_deviation is not None:

        if fair_value_deviation < -2:
            score += 1

        elif fair_value_deviation > 2:
            score -= 1

    # Structure
    if (
        resistance is not None
        and price is not None
        and price > resistance
    ):
        score += 1

    if (
        support is not None
        and price is not None
        and price < support
    ):
        score -= 1

    if score >= 4:
        return "BUY"

    if score <= -4:
        return "SELL"

    return "HOLD"


# ============================================================
# SIGNAL REASONS
# ============================================================

def generate_signal_reasons(
    signal,
    trend,
    rsi,
    macd,
    momentum,
    ema_fast,
    ema_slow,
    fair_value_deviation,
    price,
    support,
    resistance,
    market_score
):

    bullish_reasons = []
    bearish_reasons = []
    warnings = []

    if trend == "صعودی":

        bullish_reasons.append(
            "روند کوتاه‌مدت صعودی است"
        )

    elif trend == "نزولی":

        bearish_reasons.append(
            "روند کوتاه‌مدت نزولی است"
        )

    if (
        ema_fast is not None
        and ema_slow is not None
    ):

        if ema_fast > ema_slow:

            bullish_reasons.append(
                "EMA سریع بالاتر از EMA کند قرار دارد"
            )

        elif ema_fast < ema_slow:

            bearish_reasons.append(
                "EMA سریع پایین‌تر از EMA کند قرار دارد"
            )

    if momentum is not None:

        if momentum > 0:

            bullish_reasons.append(
                "Momentum مثبت است"
            )

        elif momentum < 0:

            bearish_reasons.append(
                "Momentum منفی است"
            )

    if rsi is not None:

        if 55 <= rsi <= 70:

            bullish_reasons.append(
                "RSI از قدرت خریداران حمایت می‌کند"
            )

        elif 30 <= rsi <= 45:

            bearish_reasons.append(
                "RSI از قدرت فروشندگان حمایت می‌کند"
            )

        elif rsi > 75:

            warnings.append(
                "RSI در محدوده اشباع خرید است"
            )

        elif rsi < 25:

            warnings.append(
                "RSI در محدوده اشباع فروش است"
            )

    if macd:

        histogram = safe_float(
            macd.get("histogram")
        )

        if histogram is not None:

            if histogram > 0:

                bullish_reasons.append(
                    "MACD مومنتوم مثبت دارد"
                )

            elif histogram < 0:

                bearish_reasons.append(
                    "MACD مومنتوم منفی دارد"
                )

    if fair_value_deviation is not None:

        if fair_value_deviation < -2:

            bullish_reasons.append(
                "قیمت پایین‌تر از ارزش منصفانه است"
            )

        elif fair_value_deviation > 2:

            bearish_reasons.append(
                "قیمت بالاتر از ارزش منصفانه است"
            )

    if (
        resistance is not None
        and price is not None
        and price > resistance
    ):

        bullish_reasons.append(
            "قیمت مقاومت اخیر را شکسته است"
        )

    if (
        support is not None
        and price is not None
        and price < support
    ):

        bearish_reasons.append(
            "قیمت حمایت اخیر را شکسته است"
        )

    if market_score is not None:

        if market_score >= 65:

            bullish_reasons.append(
                "امتیاز کلی بازار به نفع خریداران است"
            )

        elif market_score <= 35:

            bearish_reasons.append(
                "امتیاز کلی بازار به نفع فروشندگان است"
            )

    if signal == "BUY":

        primary = bullish_reasons

    elif signal == "SELL":

        primary = bearish_reasons

    else:

        primary = (
            bullish_reasons[:2]
            + bearish_reasons[:2]
        )

    return {
        "primary": primary[:6],
        "bullish": bullish_reasons[:8],
        "bearish": bearish_reasons[:8],
        "warnings": warnings[:5],
    }


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_confidence(
    market_score,
    trend,
    trend_strength,
    signal,
    rsi,
    macd,
    fair_value_deviation,
    candle_count
):

    confidence = 50.0

    # Market score distance from neutral
    if market_score is not None:

        confidence += (
            abs(
                market_score
                - 50
            )
            * 0.30
        )

    # Trend
    if trend != "خنثی":
        confidence += 5

    # Trend strength
    if trend_strength is not None:

        confidence += (
            trend_strength
            * 0.10
        )

    # Signal
    if signal in (
        "BUY",
        "SELL"
    ):
        confidence += 5

    # RSI quality
    if rsi is not None:

        if (
            40 <= rsi <= 70
        ):
            confidence += 3

    # MACD availability
    if macd:
        confidence += 3

    # Fair value availability
    if fair_value_deviation is not None:

        if abs(
            fair_value_deviation
        ) <= 3:

            confidence += 3

    # Data quality
    if candle_count >= 60:
        confidence += 4

    elif candle_count >= 40:
        confidence += 2

    return round(
        clamp(
            confidence,
            0,
            100
        ),
        2
    )


# ============================================================
# TRADE LEVELS
# ============================================================

def calculate_trade_levels(
    price,
    signal,
    atr,
    support,
    resistance
):

    if price is None:

        return {
            "entry": None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "take_profit_3": None,
            "risk_reward": None,
        }

    volatility = safe_float(
        atr
    )

    if (
        volatility is None
        or volatility <= 0
    ):

        volatility = (
            price * 0.005
        )

    if signal == "BUY":

        entry = price

        stop_loss = (
            support
            if (
                support is not None
                and support < price
            )
            else price - (
                volatility * 1.5
            )
        )

        risk = (
            entry
            - stop_loss
        )

        if risk <= 0:
            risk = volatility

        tp1 = entry + risk
        tp2 = entry + (
            risk * 2
        )
        tp3 = entry + (
            risk * 3
        )

        reward = (
            tp2 - entry
        )

    elif signal == "SELL":

        entry = price

        stop_loss = (
            resistance
            if (
                resistance is not None
                and resistance > price
            )
            else price + (
                volatility * 1.5
            )
        )

        risk = (
            stop_loss
            - entry
        )

        if risk <= 0:
            risk = volatility

        tp1 = entry - risk
        tp2 = entry - (
            risk * 2
        )
        tp3 = entry - (
            risk * 3
        )

        reward = (
            entry - tp2
       
