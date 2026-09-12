import time
import traceback
from datetime import datetime, timezone

from dotenv import load_dotenv

from data.collectors.tgju import get_gold_18k
from data.collectors.world_gold import get_world_gold
from data.collectors.usd_toman import get_usd_toman

from database import save_market_snapshot

from candle_engine import (
    build_timeframe_candles,
)


# ============================================================
# ENV
# ============================================================

load_dotenv()


# ============================================================
# CONFIG
# ============================================================

# هر 5 دقیقه یک Snapshot
COLLECT_INTERVAL = 5 * 60

SYMBOL = "gold_18k"


# ============================================================
# TIMESTAMP
# ============================================================

def utc_now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# SAFE FLOAT
# ============================================================

def safe_float(value):
    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


# ============================================================
# NORMALIZE TGJU
# ============================================================

def normalize_tgju_price(data):
    """
    استانداردسازی قیمت طلای 18 عیار TGJU.

    خروجی نهایی همیشه تومان است.
    """

    if not data:
        return None

    price = safe_float(
        data.get("price")
    )

    if price is None or price <= 0:
        return None

    return {
        "price_toman": price,
        "timestamp": data.get(
            "timestamp"
        ),
        "source": "tgju",
    }


# ============================================================
# NORMALIZE WORLD GOLD
# ============================================================

def normalize_world_gold(data):
    """
    استانداردسازی XAU/USD.

    World Gold API:
        XAU/USD
        Troy Ounce
    """

    if not data:
        return None

    price = None

    # حالت فعلی collector
    if data.get("price_usd") is not None:
        price = data.get(
            "price_usd"
        )

    # حالت‌های احتمالی سازگار
    elif data.get("price") is not None:
        price = data.get(
            "price"
        )

    elif data.get("gold_price") is not None:
        price = data.get(
            "gold_price"
        )

    price = safe_float(price)

    if price is None or price <= 0:
        return None

    return {
        "price_usd": price,
        "timestamp": data.get(
            "timestamp"
        ),
        "source": "gold_api",
    }


# ============================================================
# NORMALIZE USD / TOMAN
# ============================================================

def normalize_usd_toman(data):
    """
    استانداردسازی دلار به تومان.

    نگه می‌داریم:
        buy
        sell
        mid
    """

    if not data:
        return None

    buy = safe_float(
        data.get(
            "buy_toman"
        )
    )

    if buy is None:
        buy = safe_float(
            data.get(
                "buy"
            )
        )

    sell = safe_float(
        data.get(
            "sell_toman"
        )
    )

    if sell is None:
        sell = safe_float(
            data.get(
                "sell"
            )
        )

    mid = safe_float(
        data.get(
            "mid_toman"
        )
    )

    if mid is None:
        mid = safe_float(
            data.get(
                "mid"
            )
        )

    # اگر Mid موجود نبود،
    # از میانگین خرید و فروش استفاده می‌کنیم.
    if (
        mid is None
        and buy is not None
        and sell is not None
    ):
        mid = (
            buy + sell
        ) / 2

    if (
        buy is None
        and sell is None
        and mid is None
    ):
        return None

    return {
        "buy_toman": buy,
        "sell_toman": sell,
        "mid_toman": mid,
        "timestamp": data.get(
            "timestamp"
        ),
        "source": "netarz",
    }


# ============================================================
# COLLECT TGJU
# ============================================================

def collect_tgju():

    try:

        print(
            "📡 TGJU: requesting gold price...",
            flush=True,
        )

        data = get_gold_18k()

        normalized = normalize_tgju_price(
            data
        )

        if not normalized:

            print(
                "🔴 TGJU: invalid data.",
                flush=True,
            )

            return None

        print(
            "🟢 TGJU: "
            f"{normalized['price_toman']:,.0f} تومان",
            flush=True,
        )

        return normalized

    except Exception as error:

        print(
            "🔴 TGJU ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return None


# ============================================================
# COLLECT WORLD GOLD
# ============================================================

def collect_world_gold():

    try:

        print(
            "📡 WORLD GOLD: requesting XAU/USD...",
            flush=True,
        )

        data = get_world_gold()

        normalized = normalize_world_gold(
            data
        )

        if not normalized:

            print(
                "🔴 WORLD GOLD: invalid data.",
                flush=True,
            )

            return None

        print(
            "🟢 WORLD GOLD: "
            f"${normalized['price_usd']:,.2f} / oz",
            flush=True,
        )

        return normalized

    except Exception as error:

        print(
            "🔴 WORLD GOLD ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return None


# ============================================================
# COLLECT USD / TOMAN
# ============================================================

def collect_usd_toman():

    try:

        print(
            "📡 USD/TOMAN: requesting FX...",
            flush=True,
        )

        data = get_usd_toman()

        normalized = normalize_usd_toman(
            data
        )

        if not normalized:

            print(
                "🔴 USD/TOMAN: invalid data.",
                flush=True,
            )

            return None

        buy = normalized.get(
            "buy_toman"
        )

        sell = normalized.get(
            "sell_toman"
        )

        mid = normalized.get(
            "mid_toman"
        )

        print(
            "🟢 USD/TOMAN:",
            flush=True,
        )

        if mid is not None:
            print(
                f"   Mid   : "
                f"{mid:,.0f} تومان",
                flush=True,
            )

        if buy is not None:
            print(
                f"   Buy   : "
                f"{buy:,.0f} تومان",
                flush=True,
            )

        if sell is not None:
            print(
                f"   Sell  : "
                f"{sell:,.0f} تومان",
                flush=True,
            )

        return normalized

    except Exception as error:

        print(
            "🔴 USD/TOMAN ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return None


# ============================================================
# SAVE MARKET SNAPSHOT
# ============================================================

def save_snapshot(
    tgju_data,
    world_gold_data,
    usd_data,
):
    """
    ذخیره یک Snapshot کامل بازار.

    هر چرخه فقط یک رکورد ساخته می‌شود.

    Servix فعلاً None است چون نباید
    هر 5 دقیقه مصرف شود.
    """

    snapshot_timestamp = utc_now_iso()

    gold_price = None
    world_gold = None

    usd_buy = None
    usd_sell = None
    usd_mid = None

    tgju_timestamp = None
    world_gold_timestamp = None
    usd_timestamp = None

    # --------------------------------------------------------
    # TGJU
    # --------------------------------------------------------

    if tgju_data:

        gold_price = tgju_data.get(
            "price_toman"
        )

        tgju_timestamp = (
            tgju_data.get(
                "timestamp"
            )
            or snapshot_timestamp
        )

    # --------------------------------------------------------
    # WORLD GOLD
    # --------------------------------------------------------

    if world_gold_data:

        world_gold = (
            world_gold_data.get(
                "price_usd"
            )
        )

        world_gold_timestamp = (
            world_gold_data.get(
                "timestamp"
            )
            or snapshot_timestamp
        )

    # --------------------------------------------------------
    # USD/TOMAN
    # --------------------------------------------------------

    if usd_data:

        usd_buy = (
            usd_data.get(
                "buy_toman"
            )
        )

        usd_sell = (
            usd_data.get(
                "sell_toman"
            )
        )

        usd_mid = (
            usd_data.get(
                "mid_toman"
            )
        )

        usd_timestamp = (
            usd_data.get(
                "timestamp"
            )
            or snapshot_timestamp
        )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if (
        gold_price is None
        and world_gold is None
        and usd_mid is None
    ):

        print(
            "❌ SNAPSHOT: "
            "No usable market data.",
            flush=True,
        )

        return False

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    try:

        save_market_snapshot(

            timestamp=snapshot_timestamp,

            gold_18k_toman=gold_price,

            world_gold_usd=world_gold,

            usd_buy_toman=usd_buy,

            usd_sell_toman=usd_sell,

            usd_mid_toman=usd_mid,

            # Servix فعلاً در چرخه 5 دقیقه‌ای
            # استفاده نمی‌شود.
            servix_gold_18k_toman=None,

            servix_timestamp=None,

            tgju_timestamp=tgju_timestamp,

            world_gold_timestamp=(
                world_gold_timestamp
            ),

            usd_timestamp=usd_timestamp,
        )

        print(
            "💾 SNAPSHOT: "
            "Market snapshot saved.",
            flush=True,
        )

        return True

    except Exception as error:

        print(
            "❌ SNAPSHOT SAVE ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return False


# ============================================================
# BUILD CANDLES
# ============================================================

def update_candles():

    for timeframe in [
        "5m",
        "15m",
        "1h",
    ]:

        try:

            candles = build_timeframe_candles(

                timeframe=timeframe,

                symbol=SYMBOL,

                limit=500,
            )

            print(
                f"🕯️ CANDLE: "
                f"{timeframe} updated "
                f"({len(candles)} candles)",
                flush=True,
            )

        except Exception as error:

            print(
                f"❌ CANDLE {timeframe}: "
                f"{type(error).__name__}: "
                f"{error}",
                flush=True,
            )


# ============================================================
# COLLECT ONE CYCLE
# ============================================================

def collect_once():

    print(
        "",
        flush=True,
    )

    print(
        "========================================",
        flush=True,
    )

    print(
        "📡 MARKET COLLECTOR: "
        "New 5-minute cycle",
        flush=True,
    )

    print(
        "========================================",
        flush=True,
    )

    # --------------------------------------------------------
    # COLLECT SOURCES
    # --------------------------------------------------------

    tgju_data = collect_tgju()

    world_gold_data = (
        collect_world_gold()
    )

    usd_data = collect_usd_toman()

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    active_sources = sum(
        1
        for source in [
            tgju_data,
            world_gold_data,
            usd_data,
        ]
        if source is not None
    )

    print(
        f"📊 ACTIVE SOURCES: "
        f"{active_sources}/3",
        flush=True,
    )

    # --------------------------------------------------------
    # SAVE SNAPSHOT
    # --------------------------------------------------------

    saved = save_snapshot(

        tgju_data=tgju_data,

        world_gold_data=world_gold_data,

        usd_data=usd_data,
    )

    if not saved:

        print(
            "⚠️ COLLECTOR: "
            "Snapshot was not saved.",
            flush=True,
        )

        return

    # --------------------------------------------------------
    # BUILD CANDLES
    # --------------------------------------------------------

    update_candles()

    print(
        "✅ COLLECTOR: "
        "5-minute cycle finished.",
        flush=True,
    )


# ============================================================
# COLLECTOR LOOP
# ============================================================

def run_collector():

    print(
        "🤖 MARKET COLLECTOR SERVICE STARTED",
        flush=True,
    )

    print(
        f"⏱️ Collection interval: "
        f"{COLLECT_INTERVAL} seconds "
        f"(5 minutes)",
        flush=True,
    )

    print(
        "📡 Sources: "
        "TGJU + World Gold + USD/Toman",
        flush=True,
    )

    print(
        "💾 Storage: "
        "market_snapshots",
        flush=True,
    )

    print(
        "🕯️ Candles: "
        "5m / 15m / 1h",
        flush=True,
    )

    print(
        "🚫 Servix: "
        "disabled from 5-minute cycle",
        flush=True,
    )

    # --------------------------------------------------------
    # First collection immediately
    # --------------------------------------------------------

    try:

        collect_once()

    except Exception as error:

        print(
            "❌ INITIAL COLLECTOR ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        traceback.print_exc()

    # --------------------------------------------------------
    # Main loop
    # --------------------------------------------------------

    while True:

        try:

            print(
                f"⏳ COLLECTOR: "
                f"Waiting {COLLECT_INTERVAL} seconds...",
                flush=True,
            )

            time.sleep(
                COLLECT_INTERVAL
            )

            collect_once()

        except Exception as error:

            print(
                "❌ COLLECTOR ERROR:",
                flush=True,
            )

            print(
                f"Type: {type(error).__name__}",
                flush=True,
            )

            print(
                f"Message: {error}",
                flush=True,
            )

            traceback.print_exc()


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    run_collector()
