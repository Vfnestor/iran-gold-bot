import time

from data.collectors.tgju import get_gold_18k
from database import save_price
from candle_engine import build_1m_candle


# ==========================================
# Collector Settings
# ==========================================

COLLECT_INTERVAL = 10


# ==========================================
# Collect One Price
# ==========================================

def collect_once():

    print(
        "📡 COLLECTOR: Requesting price from TGJU..."
    )

    data = get_gold_18k()

    print(
        "📥 COLLECTOR: Price received: "
        f"{data['price']:,} "
        f"{data['currency']}"
    )

    # ذخیره داده خام
    save_price(data)

    print(
        "💾 COLLECTOR: Raw price saved."
    )

    # ساخت/به‌روزرسانی کندل 1 دقیقه‌ای
    try:

        candle = build_1m_candle(
            symbol=data["symbol"]
        )

        if candle:

            print(
                "🕯️ COLLECTOR: 1M candle updated."
            )

    except Exception as error:

        print(
            "❌ COLLECTOR: Candle engine error: "
            f"{type(error).__name__}: {error}"
        )


# ==========================================
# Collector Service
# ==========================================

def run_collector():

    print(
        "🤖 COLLECTOR SERVICE STARTED"
    )

    print(
        f"⏱️ Collection interval: "
        f"{COLLECT_INTERVAL} seconds"
    )

    while True:

        try:

            collect_once()

        except Exception as error:

            print(
                "❌ COLLECTOR ERROR: "
                f"{type(error).__name__}: {error}"
            )

        print(
            f"⏳ COLLECTOR: Waiting "
            f"{COLLECT_INTERVAL} seconds..."
        )

        time.sleep(
            COLLECT_INTERVAL
        )


# ==========================================
# Direct Execution
# ==========================================

if __name__ == "__main__":

    run_collector()
