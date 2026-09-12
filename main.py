import os
import threading
import traceback
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from http.server import BaseHTTPRequestHandler, HTTPServer

from data.collector_service import run_collector
from data.collectors.tgju import get_gold_18k
from data.collectors.world_gold import get_world_gold
from data.collectors.usd_toman import get_usd_toman

from database import (
    init_db,
    get_latest_market_snapshot,
    get_market_history,
    get_analysis_history,
    get_latest_analysis,
    get_database_stats,
)

from candle_engine import get_recent_candles

from analysis.analysis_engine import (
    run_analysis,
    format_analysis_summary,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

print(
    "DEBUG 1: main.py started",
    flush=True,
)


# ============================================================
# CONFIG
# ============================================================

ANALYSIS_INTERVAL = 5 * 60


# ============================================================
# ADMIN
# ============================================================

def get_admin_user_id():
    value = os.getenv(
        "ADMIN_USER_ID",
        "",
    ).strip()

    if not value:
        return None

    try:
        return int(value)

    except ValueError:
        print(
            "⚠️ ADMIN_USER_ID is invalid.",
            flush=True,
        )
        return None


def is_admin(update: Update):
    admin_id = get_admin_user_id()

    if admin_id is None:
        return False

    if not update.effective_user:
        return False

    return update.effective_user.id == admin_id


# ============================================================
# DATABASE ROW HELPERS
# ============================================================

def snapshot_to_dict(row):
    """
    Convert market_snapshots database tuple to dictionary.
    Supports both tuple and dict formats.
    """

    if row is None:
        return None

    if isinstance(row, dict):
        return row

    if isinstance(row, tuple):
        columns = [
            "id",
            "timestamp",
            "gold_18k_toman",
            "world_gold_usd",
            "usd_buy_toman",
            "usd_sell_toman",
            "usd_mid_toman",
            "servix_gold_18k_toman",
            "servix_timestamp",
            "tgju_timestamp",
            "world_gold_timestamp",
            "usd_timestamp",
            "created_at",
        ]

        return dict(zip(columns, row))

    return None


def analysis_to_dict(row):
    """
    Convert analysis_history database tuple to dictionary.
    Supports both tuple and dict formats.
    """

    if row is None:
        return None

    if isinstance(row, dict):
        return row

    if isinstance(row, tuple):
        columns = [
            "id",
            "timestamp",
            "symbol",
            "price_toman",
            "signal",
            "trend",
            "confidence",
            "entry",
            "stop_loss",
            "take_profit_1",
            "take_profit_2",
            "take_profit_3",
            "risk_reward",
            "rsi",
            "macd",
            "macd_signal",
            "ema_fast",
            "ema_slow",
            "atr",
            "momentum",
            "support",
            "resistance",
            "world_gold_usd",
            "usd_mid_toman",
            "fair_value_toman",
            "source_spread",
            "analysis_data",
            "created_at",
        ]

        return dict(zip(columns, row))

    return None


# ============================================================
# HELPERS
# ============================================================

def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def format_timestamp(timestamp):
    if not timestamp:
        return "زمان نامشخص"

    try:
        dt = datetime.fromisoformat(
            str(timestamp).replace(
                "Z",
                "+00:00",
            )
        )

        return dt.strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    except Exception:
        return str(timestamp)


# ============================================================
# PRICE HELPERS
# ============================================================

def get_tgju_toman(data):
    if not isinstance(data, dict):
        raise ValueError("TGJU response is not a dictionary.")

    if data.get("price_toman") is not None:
        return float(data["price_toman"])

    if data.get("price") is None:
        raise ValueError("TGJU price not found.")

    price = float(data["price"])

    currency = str(
        data.get(
            "currency",
            "",
        )
    ).upper()

    if currency in (
        "IRR",
        "RLS",
        "RIAL",
        "ریال",
    ):
        return price / 10

    if price > 100_000_000:
        return price / 10

    return price


def extract_source_timestamp(data, fallback=None):
    if not isinstance(data, dict):
        return fallback

    for key in (
        "timestamp",
        "time",
        "datetime",
        "date",
        "updated_at",
        "created_at",
    ):
        value = data.get(key)

        if value:
            return value

    return fallback


def find_latest_history_value(
    history,
    value_key,
    timestamp_key=None,
):
    if not history:
        return None, None

    for row in history:
        item = snapshot_to_dict(row)

        if not item:
            continue

        value = item.get(value_key)

        if value is None:
            continue

        timestamp = (
            item.get(timestamp_key)
            if timestamp_key
            else item.get("timestamp")
        )

        return value, timestamp

    return None, None


def get_latest_saved_source_data():
    try:
        history = get_market_history(
            limit=100
        )

        if not history:
            return {}

        data = {}

        data["tgju"] = find_latest_history_value(
            history,
            "gold_18k_toman",
            "tgju_timestamp",
        )

        data["world"] = find_latest_history_value(
            history,
            "world_gold_usd",
            "world_gold_timestamp",
        )

        data["usd_mid"] = find_latest_history_value(
            history,
            "usd_mid_toman",
            "usd_timestamp",
        )

        data["usd_buy"] = find_latest_history_value(
            history,
            "usd_buy_toman",
            "usd_timestamp",
        )

        data["usd_sell"] = find_latest_history_value(
            history,
            "usd_sell_toman",
            "usd_timestamp",
        )

        data["servix"] = find_latest_history_value(
            history,
            "servix_gold_18k_toman",
            "servix_timestamp",
        )

        return data

    except Exception as error:
        print(
            "⚠️ Could not read source history:",
            error,
            flush=True,
        )

        return {}


# ============================================================
# LIVE PRICE COLLECTION
# ============================================================

def get_live_price_sources():
    saved = get_latest_saved_source_data()

    results = []

    # ========================================================
    # TGJU
    # ========================================================

    try:
        data = get_gold_18k()

        price = get_tgju_toman(data)

        timestamp = extract_source_timestamp(
            data,
            current_timestamp(),
        )

        results.append({
            "name": "TGJU",
            "icon": "🟢",
            "ok": True,
            "price": price,
            "timestamp": timestamp,
            "text": (
                f"💰 {price:,.0f} تومان\n"
                f"   🕐 {format_timestamp(timestamp)}"
            ),
        })

    except Exception as error:
        print(
            f"❌ PRICE TGJU FAILED: {error}",
            flush=True,
        )

        price, timestamp = saved.get(
            "tgju",
            (None, None),
        )

        if price is not None:
            results.append({
                "name": "TGJU",
                "icon": "🔴",
                "ok": False,
                "price": price,
                "timestamp": timestamp,
                "text": (
                    f"💰 آخرین قیمت: "
                    f"{float(price):,.0f} تومان\n"
                    f"   🕐 {format_timestamp(timestamp)}\n"
                    f"   ⚠️ پاسخ جدید دریافت نشد"
                ),
            })

        else:
            results.append({
                "name": "TGJU",
                "icon": "🔴",
                "ok": False,
                "price": None,
                "timestamp": None,
                "text": "⚠️ قیمت ذخیره‌شده‌ای وجود ندارد",
            })

    # ========================================================
    # WORLD GOLD
    # ========================================================

    try:
        data = get_world_gold()

        price = float(data["price_usd"])

        timestamp = extract_source_timestamp(
            data,
            current_timestamp(),
        )

        results.append({
            "name": "World Gold",
            "icon": "🟢",
            "ok": True,
            "price": price,
            "timestamp": timestamp,
            "text": (
                f"🌎 ${price:,.2f} / oz\n"
                f"   🕐 {format_timestamp(timestamp)}"
            ),
        })

    except Exception as error:
        print(
            f"❌ PRICE WORLD GOLD FAILED: {error}",
            flush=True,
        )

        price, timestamp = saved.get(
            "world",
            (None, None),
        )

        if price is not None:
            results.append({
                "name": "World Gold",
                "icon": "🔴",
                "ok": False,
                "price": price,
                "timestamp": timestamp,
                "text": (
                    f"🌎 آخرین قیمت: "
                    f"${float(price):,.2f} / oz\n"
                    f"   🕐 {format_timestamp(timestamp)}\n"
                    f"   ⚠️ پاسخ جدید دریافت نشد"
                ),
            })

        else:
            results.append({
                "name": "World Gold",
                "icon": "🔴",
                "ok": False,
                "price": None,
                "timestamp": None,
                "text": "⚠️ قیمت ذخیره‌شده‌ای وجود ندارد",
            })

    # ========================================================
    # USD / TOMAN
    # ========================================================

    try:
        data = get_usd_toman()

        usd_mid = float(
            data.get(
                "mid",
                data.get("mid_toman"),
            )
        )

        usd_buy = float(
            data.get(
                "buy",
                data.get("buy_toman"),
            )
        )

        usd_sell = float(
            data.get(
                "sell",
                data.get("sell_toman"),
            )
        )

        timestamp = extract_source_timestamp(
            data,
            current_timestamp(),
        )

        results.append({
            "name": "NetArz",
            "icon": "🟢",
            "ok": True,
            "price": usd_mid,
            "timestamp": timestamp,
            "text": (
                f"💵 میانگین: {usd_mid:,.0f} تومان\n"
                f"   خرید: {usd_buy:,.0f} تومان\n"
                f"   فروش: {usd_sell:,.0f} تومان\n"
                f"   🕐 {format_timestamp(timestamp)}"
            ),
        })

    except Exception as error:
        print(
            f"❌ PRICE USD/TOMAN FAILED: {error}",
            flush=True,
        )

        mid, timestamp = saved.get(
            "usd_mid",
            (None, None),
        )

        buy, _ = saved.get(
            "usd_buy",
            (None, None),
        )

        sell, _ = saved.get(
            "usd_sell",
            (None, None),
        )

        if mid is not None:
            buy_text = (
                f"{float(buy):,.0f}"
                if buy is not None
                else "—"
            )

            sell_text = (
                f"{float(sell):,.0f}"
                if sell is not None
                else "—"
            )

            results.append({
                "name": "NetArz",
                "icon": "🔴",
                "ok": False,
                "price": mid,
                "timestamp": timestamp,
                "text": (
                    f"💵 آخرین میانگین: "
                    f"{float(mid):,.0f} تومان\n"
                    f"   خرید: {buy_text} تومان\n"
                    f"   فروش: {sell_text} تومان\n"
                    f"   🕐 {format_timestamp(timestamp)}\n"
                    f"   ⚠️ پاسخ جدید دریافت نشد"
                ),
            })

        else:
            results.append({
                "name": "NetArz",
                "icon": "🔴",
                "ok": False,
                "price": None,
                "timestamp": None,
                "text": "⚠️ قیمت ذخیره‌شده‌ای وجود ندارد",
            })

    # ========================================================
    # SERVIX
    # ========================================================

    try:
        from data.collectors.servix import get_servix_gold

        data = get_servix_gold()

        price = float(data["price_toman"])

        timestamp = extract_source_timestamp(
            data,
            current_timestamp(),
        )

        results.append({
            "name": "Servix",
            "icon": "🟢",
            "ok": True,
            "price": price,
            "timestamp": timestamp,
            "text": (
                f"💰 {price:,.0f} تومان\n"
                f"   🕐 {format_timestamp(timestamp)}"
            ),
        })

    except Exception as error:
        print(
            f"❌ PRICE SERVIX FAILED: {error}",
            flush=True,
        )

        price, timestamp = saved.get(
            "servix",
            (None, None),
        )

        if price is not None:
            results.append({
                "name": "Servix",
                "icon": "🔴",
                "ok": False,
                "price": price,
                "timestamp": timestamp,
                "text": (
                    f"💰 آخرین قیمت: "
                    f"{float(price):,.0f} تومان\n"
                    f"   🕐 {format_timestamp(timestamp)}\n"
                    f"   ⚠️ پاسخ جدید دریافت نشد"
                ),
            })

        else:
            results.append({
                "name": "Servix",
                "icon": "🔴",
                "ok": False,
                "price": None,
                "timestamp": None,
                "text": "⚠️ قیمت ذخیره‌شده‌ای وجود ندارد",
            })

    return results


# ============================================================
# TEST ALL SOURCES
# ============================================================

def test_all_sources():
    results = []

    # ========================================================
    # TGJU
    # ========================================================

    try:
        print(
            "🧪 TGJU: starting test...",
            flush=True,
        )

        tgju_data = get_gold_18k()

        tgju_price_toman = get_tgju_toman(
            tgju_data
        )

        results.append({
            "name": "TGJU",
            "ok": True,
            "message": (
                f"💰 {tgju_price_toman:,.0f} تومان"
            ),
        })

        print(
            f"✅ TGJU: {tgju_price_toman:,.0f} تومان",
            flush=True,
        )

    except Exception as error:
        print(
            f"❌ TGJU TEST FAILED: {error}",
            flush=True,
        )

        results.append({
            "name": "TGJU",
            "ok": False,
            "message": str(error),
        })

    # ========================================================
    # SERVIX
    # ========================================================

    try:
        print(
            "🧪 SERVIX: starting test...",
            flush=True,
        )

        from data.collectors.servix import get_servix_gold

        servix_data = get_servix_gold()

        servix_price_toman = float(
            servix_data["price_toman"]
        )

        results.append({
            "name": "Servix",
            "ok": True,
            "message": (
                f"💰 {servix_price_toman:,.0f} تومان"
            ),
        })

        print(
            f"✅ SERVIX: {servix_price_toman:,.0f} تومان",
            flush=True,
        )

    except Exception as error:
        print(
            f"❌ SERVIX TEST FAILED: {error}",
            flush=True,
        )

        results.append({
            "name": "Servix",
            "ok": False,
            "message": str(error),
        })

    # ========================================================
    # WORLD GOLD
    # ========================================================

    try:
        print(
            "🧪 WORLD GOLD: starting test...",
            flush=True,
        )

        world_data = get_world_gold()

        world_price = float(
            world_data["price_usd"]
        )

        results.append({
            "name": "World Gold",
            "ok": True,
            "message": (
                f"🌎 ${world_price:,.2f} / oz"
            ),
        })

        print(
            f"✅ WORLD GOLD: ${world_price:,.2f} / oz",
            flush=True,
        )

    except Exception as error:
        print(
            f"❌ WORLD GOLD TEST FAILED: {error}",
            flush=True,
        )

        results.append({
            "name": "World Gold",
            "ok": False,
            "message": str(error),
        })

    # ========================================================
    # USD / TOMAN
    # ========================================================

    try:
        print(
            "🧪 USD/TOMAN: starting test...",
            flush=True,
        )

        usd_data = get_usd_toman()

        usd_mid = float(
            usd_data.get(
                "mid",
                usd_data.get("mid_toman"),
            )
        )

        usd_buy = float(
            usd_data.get(
                "buy",
                usd_data.get("buy_toman"),
            )
        )

        usd_sell = float(
            usd_data.get(
                "sell",
                usd_data.get("sell_toman"),
            )
        )

        results.append({
            "name": "USD/Toman",
            "ok": True,
            "message": (
                f"💵 Mid: {usd_mid:,.0f} تومان\n"
                f"   خرید: {usd_buy:,.0f}\n"
                f"   فروش: {usd_sell:,.0f}"
            ),
        })

        print(
            f"✅ USD/TOMAN: {usd_mid:,.0f} تومان",
            flush=True,
        )

    except Exception as error:
        print(
            f"❌ USD/TOMAN TEST FAILED: {error}",
            flush=True,
        )

        results.append({
            "name": "USD/Toman",
            "ok": False,
            "message": str(error),
        })

    return results


# ============================================================
# TELEGRAM SOURCE TEST
# ============================================================

async def source_test_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🧪 در حال بررسی منابع...\n\n"
        "لطفاً چند ثانیه صبر کنید."
    )

    try:
        results = test_all_sources()

        lines = [
            "🧪 نتیجه تست منابع",
            "",
        ]

        online_count = 0

        for result in results:
            if result["ok"]:
                online_count += 1

                lines.append(
                    f"🟢 {result['name']}"
                )

                lines.append(
                    f"   {result['message']}"
                )

            else:
                lines.append(
                    f"🔴 {result['name']}"
                )

                lines.append(
                    f"   ⚠️ {result['message']}"
                )

            lines.append("")

        lines.append(
            "━━━━━━━━━━━━━━━━"
        )

        lines.append(
            f"📊 وضعیت: "
            f"{online_count}/{len(results)} منبع فعال"
        )

        await update.message.reply_text(
            "\n".join(lines)
        )

    except Exception as error:
        print(
            "❌ SOURCE TEST COMMAND ERROR:",
            error,
            flush=True,
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا هنگام تست منابع."
        )


# ============================================================
# SYSTEM STATUS - ADMIN ONLY
# ============================================================

async def system_status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(update):
        await update.message.reply_text(
            "⛔ دسترسی غیرمجاز."
        )

        print(
            "⚠️ Unauthorized system status access attempt.",
            flush=True,
        )

        return

    try:
        stats = get_database_stats()

        latest_snapshot = snapshot_to_dict(
            get_latest_market_snapshot()
        )

        latest_analysis = analysis_to_dict(
            get_latest_analysis()
        )

        candles_5m = get_recent_candles(
            timeframe="5m",
            limit=1,
        )

        candles_15m = get_recent_candles(
            timeframe="15m",
            limit=1,
        )

        candles_1h = get_recent_candles(
            timeframe="1h",
            limit=1,
        )

        total_snapshots = stats.get(
            "total_market_snapshots",
            0,
        )

        total_analyses = stats.get(
            "total_analyses",
            0,
        )

        total_prices = stats.get(
            "total_prices",
            0,
        )

        total_candles = stats.get(
            "total_candles",
            0,
        )

        if latest_snapshot:
            latest_price = latest_snapshot.get(
                "gold_18k_toman"
            )

            latest_snapshot_time = latest_snapshot.get(
                "timestamp",
                "نامشخص",
            )

            if latest_price is not None:
                latest_price_text = (
                    f"{float(latest_price):,.0f} تومان"
                )
            else:
                latest_price_text = "نامشخص"

        else:
            latest_price_text = "هنوز وجود ندارد"
            latest_snapshot_time = "—"

        if latest_analysis:
            latest_signal = latest_analysis.get(
                "signal",
                "HOLD",
            )

            latest_trend = latest_analysis.get(
                "trend",
                "خنثی",
            )

            latest_confidence = latest_analysis.get(
                "confidence"
            )

            if latest_confidence is not None:
                latest_confidence_text = (
                    f"{float(latest_confidence):.0f}%"
                )
            else:
                latest_confidence_text = "—"

        else:
            latest_signal = "هنوز وجود ندارد"
            latest_trend = "—"
            latest_confidence_text = "—"

        candle_5m_status = (
            "🟢 فعال"
            if candles_5m
            else "🟡 در انتظار داده"
        )

        candle_15m_status = (
            "🟢 فعال"
            if candles_15m
            else "🟡 در انتظار داده"
        )

        candle_1h_status = (
            "🟢 فعال"
            if candles_1h
            else "🟡 در انتظار داده"
        )

        analysis_target = 25

        if total_candles >= analysis_target:
            analysis_progress = (
                f"🟢 {analysis_target}/{analysis_target} "
                "یا بیشتر"
            )
        else:
            analysis_progress = (
                f"🟡 {total_candles}/{analysis_target} "
                "کندل"
            )

        lines = [
            "🖥 وضعیت سیستم Iran Gold AI",
            "",
            "🔐 سطح دسترسی: ADMIN",
            "━━━━━━━━━━━━━━━━",
            "",
            "📡 جمع‌آوری داده",
            "🟢 Collector: فعال",
            "⏱ دوره جمع‌آوری: هر ۵ دقیقه",
            f"📦 Market Snapshot: {total_snapshots}",
            f"🕐 آخرین Snapshot: {latest_snapshot_time}",
            "",
            "💰 آخرین قیمت",
            f"   {latest_price_text}",
            "",
            "🕯 موتور کندل",
            f"5m:  {candle_5m_status}",
            f"15m: {candle_15m_status}",
            f"1h:  {candle_1h_status}",
            "",
            f"📊 کندل‌های موجود: {total_candles}",
            f"🎯 پیشرفت تحلیل: {analysis_progress}",
            "",
            "🧠 موتور تحلیل",
            "🟢 فعال",
            f"📊 تحلیل‌های ثبت‌شده: {total_analyses}",
            f"🎯 آخرین Signal: {latest_signal}",
            f"📈 آخرین Trend: {latest_trend}",
            f"📊 Confidence: {latest_confidence_text}",
            "",
            "📡 منابع داده",
            "🟢 TGJU",
            "🟢 World Gold API",
            "🟢 NetArz USD/Toman",
            "🟡 Servix: فقط تست دستی",
            "",
            "💾 دیتابیس",
            "🟢 فعال",
            f"📦 Snapshot: {total_snapshots}",
            f"🕯 Candle: {total_candles}",
            f"🧠 Analysis: {total_analyses}",
            "",
            "ℹ️ Legacy",
            f"قیمت‌های قدیمی: {total_prices}",
            "",
            "━━━━━━━━━━━━━━━━",
            "🤖 Iran Gold AI",
        ]

        await update.message.reply_text(
            "\n".join(lines)
        )

    except Exception as error:
        print(
            "❌ SYSTEM STATUS ERROR:",
            error,
            flush=True,
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا در دریافت وضعیت سیستم."
        )


# ============================================================
# HEALTH CHECK SERVER
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)

        self.send_header(
            "Content-type",
            "text/plain",
        )

        self.end_headers()

        self.wfile.write(
            b"Iran Gold AI is running."
        )

    def log_message(
        self,
        format,
        *args,
    ):
        return


def start_health_server():
    try:
        port = int(
            os.getenv(
                "PORT",
                "10000",
            )
        )

        server = HTTPServer(
            ("0.0.0.0", port),
            HealthHandler,
        )

        print(
            f"🌐 Health server running on port {port}",
            flush=True,
        )

        server.serve_forever()

    except Exception as error:
        print(
            "❌ Health server failed:",
            error,
            flush=True,
        )


# ============================================================
# TELEGRAM MENU
# ============================================================

def get_main_keyboard(admin=False):
    keyboard = [
        [
            KeyboardButton("🟡 قیمت لحظه‌ای"),
            KeyboardButton("📊 تاریخچه"),
        ],
        [
            KeyboardButton("📈 کندل‌ها"),
            KeyboardButton("🧠 تحلیل"),
        ],
        [
            KeyboardButton("🧪 تست منابع"),
            KeyboardButton("ℹ️ درباره"),
        ],
    ]

    if admin:
        keyboard.append(
            [
                KeyboardButton("🖥 وضعیت سیستم")
            ]
        )

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
    )


# ============================================================
# START COMMAND
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    admin = is_admin(update)

    await update.message.reply_text(
        "🤖 به Iran Gold AI خوش آمدید.\n\n"
        "سیستم هوشمند تحلیل بازار طلای ایران.\n\n"
        "یک گزینه را انتخاب کنید:",
        reply_markup=get_main_keyboard(
            admin=admin
        ),
    )


# ============================================================
# PRICE COMMAND
# ============================================================

async def price_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        await update.message.reply_text(
            "🟡 در حال دریافت آخرین وضعیت منابع...\n\n"
            "لطفاً چند ثانیه صبر کنید."
        )

        results = get_live_price_sources()

        lines = [
            "🟡 قیمت لحظه‌ای بازار",
            "",
            "━━━━━━━━━━━━━━━━",
        ]

        online_count = 0

        for result in results:
            if result["ok"]:
                online_count += 1

            lines.append(
                f"{result['icon']} {result['name']}"
            )

            lines.append(
                f"   {result['text']}"
            )

            lines.append(
                "━━━━━━━━━━━━━━━━"
            )

        lines.append(
            f"📊 وضعیت منابع: "
            f"{online_count}/{len(results)} پاسخ فعال"
        )

        lines.append("")

        lines.append(
            "ℹ️ قیمت قرمز یعنی منبع در درخواست فعلی "
            "پاسخ نداده و آخرین مقدار ذخیره‌شده نمایش داده شده است."
        )

        await update.message.reply_text(
            "\n".join(lines)
        )

    except Exception as error:
        print(
            "❌ PRICE COMMAND ERROR:",
            error,
            flush=True,
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا در دریافت قیمت منابع."
        )


# ============================================================
# HISTORY COMMAND
# ============================================================

async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        analyses = get_analysis_history(
            limit=10
        )

        if not analyses:
            await update.message.reply_text(
                "📊 هنوز تحلیل ثبت‌شده‌ای "
                "در دیتابیس وجود ندارد.\n\n"
                "بعد از جمع شدن داده کافی، "
                "تاریخچه تحلیل‌ها اینجا نمایش داده می‌شود."
            )

            return

        lines = [
            "📊 تاریخچه تحلیل‌های Iran Gold AI",
            "",
        ]

        for index, item in enumerate(
            analyses,
            start=1,
        ):
            item = analysis_to_dict(item)

            if not item:
                continue

            price = item.get(
                "price_toman"
            )

            confidence = item.get(
                "confidence"
            )

            signal = item.get(
                "signal",
                "HOLD",
            )

            trend = item.get(
                "trend",
                "خنثی",
            )

            timestamp = item.get(
                "timestamp",
                "",
            )

            price_text = (
                f"{float(price):,.0f} تومان"
                if price is not None
                else "نامشخص"
            )

            confidence_text = (
                f"{float(confidence):.0f}%"
                if confidence is not None
                else "—"
            )

            lines.append(
                f"{index}. 💰 {price_text}\n"
                f"   🎯 {signal} | "
                f"📈 {trend} | "
                f"📊 {confidence_text}\n"
                f"   🕐 {timestamp}"
            )

            lines.append(
                "━━━━━━━━━━━━━━━━"
            )

        await update.message.reply_text(
            "\n".join(lines)
        )

    except Exception as error:
        print(
            "❌ HISTORY ERROR:",
            error,
            flush=True,
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا در دریافت تاریخچه تحلیل."
        )


# ============================================================
# CANDLE COMMAND
# ============================================================

async def candle_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        messages = []

        for timeframe in (
            "5m",
            "15m",
            "1h",
        ):
            candles = get_recent_candles(
                timeframe=timeframe,
                limit=1,
            )

            if not candles:
                messages.append(
                    f"🕯️ {timeframe}: "
                    "هنوز کندلی وجود ندارد."
                )

                continue

            candle = candles[0]

            if isinstance(candle, tuple):
                candle = dict(candle)

            open_price = candle.get("open")
            high_price = candle.get("high")
            low_price = candle.get("low")
            close_price = candle.get("close")

            messages.append(
                f"🕯️ کندل {timeframe}\n"
                f"   O: {float(open_price):,.0f}\n"
                f"   H: {float(high_price):,.0f}\n"
                f"   L: {float(low_price):,.0f}\n"
                f"   C: {float(close_price):,.0f}"
            )

        await update.message.reply_text(
            "📈 آخرین کندل‌ها\n\n"
            + "\n\n".join(messages)
        )

    except Exception as error:
        print(
            "❌ CANDLE COMMAND ERROR:",
            error,
            flush=True,
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا در دریافت کندل‌ها."
        )


# ============================================================
# ANALYSIS COMMAND
# ============================================================

async def analysis_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🧠 در حال انجام تحلیل بازار...\n\n"
        "لطفاً چند ثانیه صبر کنید."
    )

    try:
        analysis = run_analysis()

        if not analysis:
            await update.message.reply_text(
                "⚠️ هنوز داده کافی برای تحلیل وجود ندارد.\n\n"
                "سیستم باید ابتدا چند کندل ۵ دقیقه‌ای "
                "جمع‌آوری کند."
            )

            return

        message = format_analysis_summary(
            analysis
        )

        await update.message.reply_text(
            message
        )

    except Exception as error:
        print(
            "❌ ANALYSIS COMMAND ERROR:",
            error,
            flush=True,
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا در انجام تحلیل."
        )


# ============================================================
# ABOUT COMMAND
# ============================================================

async def about_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🤖 Iran Gold AI\n\n"
        "سیستم هوشمند جمع‌آوری، "
        "اعتبارسنجی و تحلیل قیمت طلای ایران.\n\n"
        "📡 منابع داده\n"
        "• TGJU\n"
        "• Servix\n"
        "• World Gold API\n"
        "• NetArz USD/Toman\n\n"
        "🌎 داده جهانی\n"
        "• XAU/USD\n"
        "• قیمت هر اونس تروا\n\n"
        "💵 داده ارزی\n"
        "• دلار / تومان\n"
        "• نرخ خرید\n"
        "• نرخ فروش\n"
        "• نرخ میانگین\n\n"
        "🔄 جمع‌آوری بازار\n"
        "• هر ۵ دقیقه\n"
        "• ذخیره Market Snapshot\n"
        "• ساخت کندل ۵ دقیقه‌ای\n"
        "• ساخت کندل ۱۵ دقیقه‌ای\n"
        "• ساخت کندل ۱ ساعته\n\n"
        "🧠 موتور تحلیل\n"
        "• EMA\n"
        "• RSI\n"
        "• MACD\n"
        "• ATR\n"
        "• Momentum\n"
        "• Support / Resistance\n"
        "• Fair Value\n"
        "• Trend\n"
        "• Signal\n"
        "• Confidence\n"
        "• Entry / SL / TP\n\n"
        "🗄️ وضعیت سیستم\n"
        "• دیتابیس: فعال\n"
        "• جمع‌آوری داده: فعال\n"
        "• موتور کندل: فعال\n"
        "• موتور تحلیل: فعال\n\n"
        "🚀 هدف Iran Gold AI:\n"
        "ارائه تحلیل داده‌محور و قابل اعتماد "
        "برای بازار طلای ایران.\n\n"
        "❤️ تقدیم به دختر عزیزم، پناه"
    )


# ============================================================
# TEXT HANDLER
# ============================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    text = update.message.text

    if text == "🟡 قیمت لحظه‌ای":
        await price_command(update, context)

    elif text == "📊 تاریخچه":
        await history_command(update, context)

    elif text == "📈 کندل‌ها":
        await candle_command(update, context)

    elif text == "🧠 تحلیل":
        await analysis_command(update, context)

    elif text == "🧪 تست منابع":
        await source_test_command(update, context)

    elif text == "🖥 وضعیت سیستم":
        await system_status_command(update, context)

    elif text == "ℹ️ درباره":
        await about_command(update, context)

    else:
        await update.message.reply_text(
            "❓ دستور موردنظر را از منوی پایین انتخاب کنید."
        )


# ============================================================
# COLLECTOR THREAD
# ============================================================

def start_collector():
    print(
        "🚀 COLLECTOR THREAD: starting...",
        flush=True,
    )

    try:
        run_collector()

    except Exception as error:
        print(
            "❌ COLLECTOR THREAD FAILED",
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
# ANALYSIS THREAD
# ============================================================

def start_analysis_engine():
    print(
        "🧠 ANALYSIS THREAD: starting...",
        flush=True,
    )

    while True:
        try:
            analysis = run_analysis()

            if analysis:
                print(
                    "🧠 Scheduled analysis saved.",
                    flush=True,
                )

            else:
                print(
                    "ℹ️ Scheduled analysis skipped "
                    "(not enough data yet).",
                    flush=True,
                )

        except Exception as error:
            print(
                "❌ ANALYSIS THREAD ERROR:",
                error,
                flush=True,
            )

            traceback.print_exc()

        time.sleep(
            ANALYSIS_INTERVAL
        )


# ============================================================
# MAIN
# ============================================================

def main():
    print(
        "🚀 Starting Iran Gold AI...",
        flush=True,
    )

    bot_token = os.getenv(
        "BOT_TOKEN"
    )

    if not bot_token:
        print(
            "❌ BOT_TOKEN not found.",
            flush=True,
        )

        return

    print(
        "✅ BOT_TOKEN found.",
        flush=True,
    )

    admin_id = get_admin_user_id()

    if admin_id:
        print(
            "🔐 Admin ID configured.",
            flush=True,
        )

    else:
        print(
            "⚠️ ADMIN_USER_ID not configured. "
            "Admin-only menu will be hidden.",
            flush=True,
        )

    try:
        init_db()

        print(
            "🗄️ Database initialized.",
            flush=True,
        )

    except Exception as error:
        print(
            "❌ Database initialization failed:",
            error,
            flush=True,
        )

        traceback.print_exc()

        return

    print(
        "ℹ️ SERVIX startup test disabled.",
        flush=True,
    )

    health_thread = threading.Thread(
        target=start_health_server,
        daemon=True,
    )

    health_thread.start()

    try:
        application = (
            Application
            .builder()
            .token(bot_token)
            .build()
        )

        application.add_handler(
            CommandHandler(
                "start",
                start_command,
            )
        )

        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                text_handler,
            )
        )

        print(
            "✅ Telegram application initialized.",
            flush=True,
        )

    except Exception as error:
        print(
            "❌ Telegram application initialization failed:",
            error,
            flush=True,
        )

        traceback.print_exc()

        return

    collector_thread = threading.Thread(
        target=start_collector,
        daemon=True,
    )

    collector_thread.start()

    print(
        "🟢 Collector thread started.",
        flush=True,
    )

    analysis_thread = threading.Thread(
        target=start_analysis_engine,
        daemon=True,
    )

    analysis_thread.start()

    print(
        "🧠 Analysis thread started.",
        flush=True,
    )

    print(
        "📡 Starting Telegram polling...",
        flush=True,
    )

    try:
        application.run_polling(
            drop_pending_updates=True
        )

    except Exception as error:
        print(
            "❌ Telegram polling failed.",
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
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
#gooz
