from datetime import datetime, timezone

from database import get_candles


SYMBOL = "gold_18k"
TIMEFRAME = "15m"

LOOKAHEAD_CANDLES = 12
MIN_HISTORY_SAMPLES = 20

TARGET_ATR_MULTIPLIERS = (
    0.50,
    1.00,
    1.50,
    2.00,
    2.50,
)


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_price(value):
    value = int(round(_number(value)))
    return f"{value:,}"


def _calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return None

    true_ranges = []

    for index in range(1, len(candles)):
        previous_close = _number(candles[index - 1][4])
        high = _number(candles[index][2])
        low = _number(candles[index][3])

        true_range = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close),
        )

        true_ranges.append(true_range)

    if len(true_ranges) < period:
        return None

    return sum(true_ranges[-period:]) / period


def _normalize_candles(rows):
    candles = []

    for row in rows or []:
        if isinstance(row, dict):
            candles.append(
                (
                    row.get("timestamp"),
                    row.get("open"),
                    row.get("high"),
                    row.get("low"),
                    row.get("close"),
                    row.get("volume", 0),
                )
            )
        elif isinstance(row, (tuple, list)) and len(row) >= 6:
            candles.append(tuple(row[:6]))

    # database returns newest first
    candles.reverse()

    return candles


def _historical_probability(
    candles,
    target_distance,
    stop_distance,
    direction,
):
    """
    Estimate historical probability that a target is reached
    before the stop during the next LOOKAHEAD_CANDLES candles.

    This is a historical/backtest estimate.
    It is NOT a guaranteed future probability.
    """

    if len(candles) < (
        MIN_HISTORY_SAMPLES + LOOKAHEAD_CANDLES + 15
    ):
        return None

    successful = 0
    samples = 0

    start = 14
    end = len(candles) - LOOKAHEAD_CANDLES

    for index in range(start, end):
        entry = _number(candles[index][4])

        if entry <= 0:
            continue

        if direction == "BUY":
            target = entry + target_distance
            stop = entry - stop_distance
        else:
            target = entry - target_distance
            stop = entry + stop_distance

        result = None

        for future_index in range(
            index + 1,
            index + 1 + LOOKAHEAD_CANDLES,
        ):
            high = _number(candles[future_index][2])
            low = _number(candles[future_index][3])

            if direction == "BUY":
                target_hit = high >= target
                stop_hit = low <= stop
            else:
                target_hit = low <= target
                stop_hit = high >= stop

            # Conservative rule:
            # if both happen in the same candle,
            # count the sample as unsuccessful.
            if target_hit and stop_hit:
                result = False
                break

            if target_hit:
                result = True
                break

            if stop_hit:
                result = False
                break

        if result is not None:
            samples += 1

            if result:
                successful += 1

    if samples < MIN_HISTORY_SAMPLES:
        return None

    return round(
        (successful / samples) * 100
    )


def _signal_direction(analysis):
    signal = str(
        analysis.get("signal", "")
    ).upper()

    if signal in (
        "BUY",
        "STRONG BUY",
        "LONG",
    ):
        return "BUY"

    if signal in (
        "SELL",
        "STRONG SELL",
        "SHORT",
    ):
        return "SELL"

    return "HOLD"


def _signal_title(direction):
    if direction == "BUY":
        return "🟢 سیگنال خرید طلا"

    if direction == "SELL":
        return "🔴 سیگنال فروش طلا"

    return "🟡 سیگنال خنثی طلا"


def _signal_id():
    timestamp = datetime.now(
        timezone.utc
    )

    return (
        "#TALA18_15MIN_"
        f"{timestamp.strftime('%m%d%H%M')}"
    )


def format_signal_message(analysis):
    """
    Create the Telegram professional signal message.
    """

    if not analysis:
        return (
            "⚠️ داده‌ای برای تحلیل وجود ندارد."
        )

    direction = _signal_direction(
        analysis
    )

    price = _number(
        analysis.get("price_toman")
    )

    entry = _number(
        analysis.get("entry"),
        price,
    )

    atr = _number(
        analysis.get("atr")
    )

    candles = _normalize_candles(
        get_candles(
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            limit=500,
        )
    )

    # If the analysis engine did not provide ATR,
    # calculate it directly from 15m candles.
    if atr <= 0:
        calculated_atr = _calculate_atr(
            candles
        )

        if calculated_atr:
            atr = calculated_atr

    if atr <= 0:
        atr = max(
            price * 0.003,
            1,
        )

    # Risk distance.
    stop_distance = atr * 1.20

    if direction == "BUY":
        stop_loss = entry - stop_distance
    elif direction == "SELL":
        stop_loss = entry + stop_distance
    else:
        stop_loss = entry

    targets = []

    for multiplier in TARGET_ATR_MULTIPLIERS:
        distance = atr * multiplier

        if direction == "BUY":
            target = entry + distance
        elif direction == "SELL":
            target = entry - distance
        else:
            target = entry

        targets.append(target)

    lines = [
        "UnqGold | Tala 18",
        "UniqeApps",
        "UNIQE",
        "",
        _signal_title(direction),
        "",
        f"📍 ورود: {_format_price(entry)}",
        f"🛑 حد ضرر: {_format_price(stop_loss)}",
        "",
    ]

    for index, target in enumerate(
        targets,
        start=1,
    ):
        lines.append(
            f"🎯 هدف {index}: "
            f"{_format_price(target)}"
        )

    lines.extend(
        [
            "",
            "📊 درصد احتمال برخورد اهداف "
            "بر اساس گذشته",
            "",
        ]
    )

    for index, target in enumerate(
        targets,
        start=1,
    ):
        distance = abs(
            target - entry
        )

        probability = None

        if direction in ("BUY", "SELL"):
            probability = _historical_probability(
                candles=candles,
                target_distance=distance,
                stop_distance=stop_distance,
                direction=direction,
            )

        if probability is None:
            probability_text = "داده کافی نیست"
        else:
            probability_text = f"{probability}٪"

        lines.append(
            f"هدف {index} — "
            f"{probability_text}"
        )

    lines.extend(
        [
            "",
            f"🆔 شناسه: {_signal_id()}",
        ]
    )

    return "\n".join(lines)
