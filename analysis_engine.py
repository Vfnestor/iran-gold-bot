import json
import math
import statistics
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

MIN_CANDLES_FOR_ANALYSIS = 25


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


def average(values):

    values = [
        safe_float(value)
        for value in values
        if safe_float(value) is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


# ============================================================
# PRICE EXTRACTION
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

    values = [
        safe_float(value)
        for value in values
        if safe_float(value) is not None
    ]

    if len(values) < period:
        return None

    sma = sum(
        values[:period]
    ) / period

    multiplier = 2 / (period + 1)

    ema = sma

    for price in values[period:]:

        ema = (
            (price - ema) * multiplier
        ) + ema

    return ema


# ============================================================
# RSI
# ============================================================

def calculate_rsi(values, period=14):

    values = [
        safe_float(value)
        for value in values
        if safe_float(value) is not None
    ]

    if len(values) <= period:
        return None

    gains = []
    losses = []

    for index in range(1, len(values)):

        change = (
            values[index]
            - values[index - 1]
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
            (avg_gain * (period - 1))
            + gains[index]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1))
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

    macd_values = []

    start_length = min(
        len(ema_fast_values),
        len(ema_slow_values)
    )

    for index in range(
        start_length
    ):

        fast = ema_fast_values[
            index
        ]

        slow = ema_slow_values[
            index
        ]

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

    if len(candles) < period + 1:
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
                abs(high - previous_close),
                abs(low - previous_close),
            )

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

    current = values[-1]
    previous = values[-1 - period]

    if previous == 0:
        return None

    return (
        (current - previous)
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
# MARKET SNAPSHOT
# ============================================================

def get_latest_snapshot():

    history = get_market_history(
        limit=1
    )

    if not history:
        return None

    return history[0]


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
    price,
    trend,
    rsi,
    macd,
    fair_value,
    support,
    resistance
):

    score = 0

    if trend == "صعودی":
        score += 2

    elif trend == "نزولی":
        score -= 2

    if rsi is not None:

        if 50 <= rsi <= 70:
            score += 1

        elif 30 <= rsi < 50:
            score -= 1

        elif rsi > 75:
            score -= 1

        elif rsi < 25:
            score += 1

    if macd:

        histogram = safe_float(
            macd.get("histogram")
        )

        if histogram is not None:

            if histogram > 0:
                score += 1

            elif histogram < 0:
                score -= 1

    if fair_value is not None:

        deviation = (
            (price - fair_value)
            / fair_value
        ) * 100

        if deviation < -2:
            score += 1

        elif deviation > 2:
            score -= 1

    if (
        resistance is not None
        and price > resistance
    ):
        score += 1

    if (
        support is not None
        and price < support
    ):
        score -= 1

    if score >= 4:
        return "BUY"

    if score <= -4:
        return "SELL"

    return "HOLD"


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_confidence(
    trend,
    signal,
    rsi,
    macd,
    fair_value,
    price
):

    score = 50.0

    if trend != "خنثی":
        score += 10

    if signal in (
        "BUY",
        "SELL"
    ):
        score += 10

    if rsi is not None:

        if (
            40 <= rsi <= 70
        ):
            score += 5

    if macd:

        histogram = safe_float(
            macd.get("histogram")
        )

        if histogram is not None:
            score += 5

    if (
        fair_value is not None
        and price is not None
    ):

        deviation = abs(
            (
                price
                - fair_value
            )
            / fair_value
        ) * 100

        if deviation <= 3:
            score += 5

    return min(
        max(score, 0),
        100
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

    volatility = atr

    if (
        volatility is None
        or volatility <= 0
    ):

        volatility = price * 0.005

    if signal == "BUY":

        entry = price

        stop_loss = (
            support
            if support is not None
            and support < price
            else price - (
                volatility * 1.5
            )
        )

        risk = entry - stop_loss

        if risk <= 0:
            risk = volatility

        tp1 = entry + risk
        tp2 = entry + (
            risk * 2
        )
        tp3 = entry + (
            risk * 3
        )

        reward = tp2 - entry

    elif signal == "SELL":

        entry = price

        stop_loss = (
            resistance
            if resistance is not None
            and resistance > price
            else price + (
                volatility * 1.5
            )
        )

        risk = stop_loss - entry

        if risk <= 0:
            risk = volatility

        tp1 = entry - risk
        tp2 = entry - (
            risk * 2
        )
        tp3 = entry - (
            risk * 3
        )

        reward = entry - tp2

    else:

        return {
            "entry": price,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "take_profit_3": None,
            "risk_reward": None,
        }

    risk_reward = (
        reward / risk
        if risk > 0
        else None
    )

    return {
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "take_profit_3": tp3,
        "risk_reward": risk_reward,
    }


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
# MAIN ANALYSIS
# ============================================================

def analyze_market():

    snapshots = get_market_history(
        limit=100
    )

    if not snapshots:

        print(
            "⚠️ No market snapshots available.",
            flush=True
        )

        return None

    latest = snapshots[0]

    price = safe_float(
        latest.get(
            "gold_18k_toman"
        )
    )

    world_gold = safe_float(
        latest.get(
            "world_gold_usd"
        )
    )

    usd_mid = safe_float(
        latest.get(
            "usd_mid_toman"
        )
    )

    servix_price = safe_float(
        latest.get(
            "servix_gold_18k_toman"
        )
    )

    if price is None:

        print(
            "⚠️ Latest gold price unavailable.",
            flush=True
        )

        return None

    candles = get_recent_candles(
        timeframe="5m",
        limit=100
    )

    if not candles:

        print(
            "⚠️ No 5m candles available.",
            flush=True
        )

        return None

    closes = get_closes(candles)

    if len(closes) < MIN_CANDLES_FOR_ANALYSIS:

        print(
            "⚠️ Not enough candles for analysis: "
            f"{len(closes)}/{MIN_CANDLES_FOR_ANALYSIS}",
            flush=True
        )

        return None

    ema_fast = calculate_ema(
        closes,
        EMA_FAST_PERIOD
    )

    ema_slow = calculate_ema(
        closes,
        EMA_SLOW_PERIOD
    )

    rsi = calculate_rsi(
        closes,
        RSI_PERIOD
    )

    macd = calculate_macd(
        closes
    )

    atr = calculate_atr(
        candles,
        ATR_PERIOD
    )

    momentum = calculate_momentum(
        closes,
        MOMENTUM_PERIOD
    )

    support, resistance = (
        calculate_support_resistance(
            candles,
            lookback=20
        )
    )

    fair_value = calculate_fair_value(
        world_gold,
        usd_mid
    )

    source_spread = calculate_source_spread(
        price,
        servix_price
    )

    trend = calculate_trend(
        price,
        ema_fast,
        ema_slow,
        momentum,
        rsi
    )

    signal = calculate_signal(
        price,
        trend,
        rsi,
        macd,
        fair_value,
        support,
        resistance
    )

    confidence = calculate_confidence(
        trend,
        signal,
        rsi,
        macd,
        fair_value,
        price
    )

    levels = calculate_trade_levels(
        price,
        signal,
        atr,
        support,
        resistance
    )

    timestamp = latest.get(
        "timestamp"
    )

    if not timestamp:

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

    analysis_data = {
        "timeframe": "5m",
        "snapshot_timestamp": timestamp,
        "candle_count": len(candles),
        "world_gold_usd": world_gold,
        "usd_mid_toman": usd_mid,
        "servix_gold_18k_toman": servix_price,
        "fair_value_toman": fair_value,
        "source_spread_percent": source_spread,
        "indicators": {
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "rsi": rsi,
            "macd": (
                macd.get("macd")
                if macd
                else None
            ),
            "macd_signal": (
                macd.get("signal")
                if macd
                else None
            ),
            "macd_histogram": (
                macd.get("histogram")
                if macd
                else None
            ),
            "atr": atr,
            "momentum": momentum,
        },
        "levels": {
            "support": support,
            "resistance": resistance,
            **levels,
        },
    }

    analysis = {
        "timestamp": timestamp,
        "symbol": SYMBOL,
        "price_toman": price,
        "signal": signal,
        "trend": trend,
        "confidence": confidence,

        "entry": levels["entry"],
        "stop_loss": levels["stop_loss"],

        "take_profit_1": levels[
            "take_profit_1"
        ],

        "take_profit_2": levels[
            "take_profit_2"
        ],

        "take_profit_3": levels[
            "take_profit_3"
        ],

        "risk_reward": levels[
            "risk_reward"
        ],

        "rsi": rsi,

        "macd": (
            macd.get("macd")
            if macd
            else None
        ),

        "macd_signal": (
            macd.get("signal")
            if macd
            else None
        ),

        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "atr": atr,
        "momentum": momentum,

        "support": support,
        "resistance": resistance,

        "world_gold_usd": world_gold,
        "usd_mid_toman": usd_mid,

        "fair_value_toman": fair_value,

        "source_spread": source_spread,

        "analysis_data": json.dumps(
            analysis_data,
            ensure_ascii=False
        ),
    }

    return analysis


# ============================================================
# RUN AND SAVE ANALYSIS
# ============================================================

def run_analysis():

    try:

        analysis = analyze_market()

        if not analysis:
            return None

        analysis_id = save_analysis(
            analysis
        )

        analysis["id"] = analysis_id

        print(
            "🧠 Analysis completed:",
            flush=True
        )

        print(
            f"   Price: "
            f"{analysis['price_toman']:,.0f} تومان",
            flush=True
        )

        print(
            f"   Trend: "
            f"{analysis['trend']}",
            flush=True
        )

        print(
            f"   Signal: "
            f"{analysis['signal']}",
            flush=True
        )

        print(
            f"   Confidence: "
            f"{analysis['confidence']:.1f}%",
            flush=True
        )

        return analysis

    except Exception as error:

        print(
            "❌ ANALYSIS ENGINE ERROR:",
            error,
            flush=True
        )

        return None


# ============================================================
# LATEST ANALYSIS
# ============================================================

def get_latest_market_analysis():

    try:

        from database import (
            get_latest_analysis
        )

        return get_latest_analysis()

    except Exception as error:

        print(
            "❌ Failed to get latest analysis:",
            error,
            flush=True
        )

        return None


# ============================================================
# ANALYSIS SUMMARY
# ============================================================

def format_analysis_summary(
    analysis
):

    if not analysis:
        return (
            "🧠 هنوز تحلیل قابل‌اعتمادی "
            "در دسترس نیست."
        )

    price = safe_float(
        analysis.get(
            "price_toman"
        )
    )

    confidence = safe_float(
        analysis.get(
            "confidence"
        )
    )

    fair_value = safe_float(
        analysis.get(
            "fair_value_toman"
        )
    )

    signal = analysis.get(
        "signal",
        "HOLD"
    )

    trend = analysis.get(
        "trend",
        "خنثی"
    )

    lines = [
        "🧠 تحلیل Iran Gold AI",
        "",
        (
            f"💰 قیمت: "
            f"{price:,.0f} تومان"
            if price is not None
            else "💰 قیمت: نامشخص"
        ),
        f"📈 روند: {trend}",
        f"🎯 سیگنال: {signal}",
        (
            f"📊 اطمینان: "
            f"{confidence:.1f}%"
            if confidence is not None
            else "📊 اطمینان: نامشخص"
        ),
    ]

    if fair_value is not None:

        lines.append(
            f"⚖️ ارزش منصفانه: "
            f"{fair_value:,.0f} تومان"
        )

    entry = safe_float(
        analysis.get("entry")
    )

    stop_loss = safe_float(
        analysis.get("stop_loss")
    )

    tp1 = safe_float(
        analysis.get(
            "take_profit_1"
        )
    )

    tp2 = safe_float(
        analysis.get(
            "take_profit_2"
        )
    )

    tp3 = safe_float(
        analysis.get(
            "take_profit_3"
        )
    )

    if entry is not None:

        lines.append(
            f"🎯 ورود: {entry:,.0f}"
        )

    if stop_loss is not None:

        lines.append(
            f"🛑 حد ضرر: "
            f"{stop_loss:,.0f}"
        )

    if tp1 is not None:

        lines.append(
            f"🥇 TP1: {tp1:,.0f}"
        )

    if tp2 is not None:

        lines.append(
            f"🥈 TP2: {tp2:,.0f}"
        )

    if tp3 is not None:

        lines.append(
            f"🥉 TP3: {tp3:,.0f}"
        )

    return "\n".join(lines)


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    print(
        "🧠 Iran Gold AI Analysis Engine",
        flush=True
    )

    result = run_analysis()

    if result:

        print(
            "",
            flush=True
        )

        print(
            format_analysis_summary(
                result
            ),
            flush=True
        )

    else:

        print(
            "⚠️ Analysis not available yet.",
            flush=True
        )
