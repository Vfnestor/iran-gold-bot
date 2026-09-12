import os
import threading
import traceback

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
    save_price,
    get_latest_prices,
)

from candle_engine import build_1m_candle


# ============================================================
# ENV
# ============================================================

load_dotenv()

print("DEBUG 1: main.py started", flush=True)


# ============================================================
# TGJU PRICE NORMALIZER
# ============================================================

def get_tgju_toman(data):

    if data.get("price_toman") is not None:
        return float(data["price_toman"])

    price = float(data["price"])

    currency = str(
        data.get("currency", "")
    ).upper()

    if currency in (
        "IRR",
        "RLS",
        "RIAL",
        "ریال",
    ):
        return price / 10

    # محافظ برای نسخه‌های فعلی TGJU collector
    if price > 100_000_000:
        return price / 10

    return price


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
            flush=True
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
            f"✅ TGJU: "
            f"{tgju_price_toman:,.0f} تومان",
            flush=True
        )

    except Exception as error:

        print(
            f"❌ TGJU TEST FAILED: {error}",
            flush=True
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
            flush=True
        )

        from data.collectors.servix import (
            get_servix_gold
        )

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
            f"✅ SERVIX: "
            f"{servix_price_toman:,.0f} تومان",
            flush=True
        )

    except Exception as error:

        print(
            f"❌ SERVIX TEST FAILED: {error}",
            flush=True
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
            flush=True
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
            f"✅ WORLD GOLD: "
            f"${world_price:,.2f} / oz",
            flush=True
        )

    except Exception as error:

        print(
            f"❌ WORLD GOLD TEST FAILED: {error}",
            flush=True
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
            flush=True
        )

        usd_data = get_usd_toman()

        usd_mid = float(
            usd_data["mid"]
        )

        usd_buy = float(
            usd_data["buy"]
        )

        usd_sell = float(
            usd_data["sell"]
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
            f"✅ USD/TOMAN: "
            f"{usd_mid:,.0f} تومان",
            flush=True
        )

    except Exception as error:

        print(
            f"❌ USD/TOMAN TEST FAILED: {error}",
            flush=True
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
    context: ContextTypes.DEFAULT_TYPE
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
            flush=True
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا هنگام تست منابع."
        )


# ============================================================
# HEALTH CHECK SERVER
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-type",
            "text/plain"
        )

        self.end_headers()

        self.wfile.write(
            b"Iran Gold AI is running."
        )

    def log_message(self, format, *args):
        return


def start_health_server():

    try:

        port = int(
            os.getenv(
                "PORT",
                "10000"
            )
        )

        server = HTTPServer(
            ("0.0.0.0", port),
            HealthHandler
        )

        print(
            f"🌐 Health server running on port {port}",
            flush=True
        )

        server.serve_forever()

    except Exception as error:

        print(
            "❌ Health server failed:",
            error,
            flush=True
        )


# ============================================================
# TELEGRAM COMMANDS
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [
        [
            KeyboardButton("🟡 قیمت لحظه‌ای"),
            KeyboardButton("📊 تاریخچه"),
        ],
        [
            KeyboardButton("📈 کندل‌ها"),
            KeyboardButton("🧪 تست منابع"),
        ],
        [
            KeyboardButton("ℹ️ درباره"),
        ],
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🤖 به Iran Gold AI خوش آمدید.\n\n"
        "یک گزینه را انتخاب کنید:",
        reply_markup=reply_markup
    )


# ============================================================
# PRICE COMMAND
# ============================================================

async def price_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        data = get_gold_18k()

        price = get_tgju_toman(data)

        save_price(data)

        source = data.get(
            "source",
            "TGJU"
        )

        message = (
            "🟡 قیمت لحظه‌ای طلای ۱۸ عیار\n\n"
            f"💰 قیمت: {price:,.0f} تومان\n"
            f"📡 منبع: {source}"
        )

        await update.message.reply_text(
            message
        )

    except Exception as error:

        print(
            "❌ PRICE COMMAND ERROR:",
            error,
            flush=True
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا در دریافت قیمت."
        )


# ============================================================
# HISTORY COMMAND
# ============================================================

async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        prices = get_latest_prices(10)

        if not prices:

            await update.message.reply_text(
                "📊 هنوز داده‌ای در دیتابیس وجود ندارد."
            )

            return

        lines = [
            "📊 آخرین قیمت‌های ثبت‌شده:",
            ""
        ]

        for item in prices:

            try:

                price = item["price"]

                timestamp = item.get(
                    "timestamp",
                    ""
                )

                lines.append(
                    f"💰 {price:,} | {timestamp}"
                )

            except Exception:

                lines.append(
                    str(item)
                )

        await update.message.reply_text(
            "\n".join(lines)
        )

    except Exception as error:

        print(
            "❌ HISTORY ERROR:",
            error,
            flush=True
        )

        await update.message.reply_text(
            "❌ خطا در دریافت تاریخچه."
        )


# ============================================================
# CANDLE COMMAND
# ============================================================

async def candle_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        candles = build_1m_candle()

        if not candles:

            await update.message.reply_text(
                "🕯️ هنوز کندلی ساخته نشده است."
            )

            return

        await update.message.reply_text(
            f"🕯️ تعداد کندل‌های ۱ دقیقه‌ای: "
            f"{len(candles)}"
        )

    except Exception as error:

        print(
            "❌ CANDLE COMMAND ERROR:",
            error,
            flush=True
        )

        await update.message.reply_text(
            "❌ خطا در دریافت کندل‌ها."
        )


# ============================================================
# ABOUT COMMAND
# ============================================================

async def about_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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

        "🔄 داده‌ها به‌صورت دوره‌ای "
        "دریافت و بررسی می‌شوند.\n\n"

        "🕯️ موتور تحلیل\n"
        "• کندل ۱ دقیقه‌ای\n"
        "• کندل ۵ دقیقه‌ای\n"
        "• کندل ۱۵ دقیقه‌ای\n"
        "• کندل ۱ ساعته\n\n"

        "🗄️ وضعیت سیستم\n"
        "• دیتابیس: فعال\n"
        "• جمع‌آوری داده: فعال\n"
        "• موتور کندل: فعال\n"
        "• اعتبارسنجی چندمنبعی: در حال توسعه\n\n"

        "🚀 هدف Iran Gold AI:\n"
        "ارائه داده‌های دقیق و قابل اعتماد "
        "برای تحلیل بازار طلای ایران.\n\n"

        "❤️ تقدیم به دختر عزیزم، پناه"
    )


# ============================================================
# TEXT HANDLER
# ============================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text

    if text == "🟡 قیمت لحظه‌ای":

        await price_command(
            update,
            context
        )

    elif text == "📊 تاریخچه":

        await history_command(
            update,
            context
        )

    elif text == "📈 کندل‌ها":

        await candle_command(
            update,
            context
        )

    elif text == "🧪 تست منابع":

        await source_test_command(
            update,
            context
        )

    elif text == "ℹ️ درباره":

        await about_command(
            update,
            context
        )

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
        flush=True
    )

    try:

        run_collector()

    except Exception as error:

        print(
            "❌ COLLECTOR THREAD FAILED",
            flush=True
        )

        print(
            f"Type: {type(error).__name__}",
            flush=True
        )

        print(
            f"Message: {error}",
            flush=True
        )

        traceback.print_exc()


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "🚀 Starting Iran Gold AI...",
        flush=True
    )

    # --------------------------------------------------------
    # BOT TOKEN
    # --------------------------------------------------------

    bot_token = os.getenv(
        "BOT_TOKEN"
    )

    if not bot_token:

        print(
            "❌ BOT_TOKEN not found.",
            flush=True
        )

        return

    print(
        "✅ BOT_TOKEN found.",
        flush=True
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    try:

        init_db()

        print(
            "🗄️ Database initialized.",
            flush=True
        )

    except Exception as error:

        print(
            "❌ Database initialization failed:",
            error,
            flush=True
        )

        traceback.print_exc()

        return

    # --------------------------------------------------------
    # SERVIX STARTUP TEST DISABLED
    # --------------------------------------------------------

    print(
        "ℹ️ SERVIX startup test disabled.",
        flush=True
    )

    # --------------------------------------------------------
    # HEALTH SERVER
    # --------------------------------------------------------

    health_thread = threading.Thread(
        target=start_health_server,
        daemon=True
    )

    health_thread.start()

    # --------------------------------------------------------
    # TELEGRAM APPLICATION
    # --------------------------------------------------------

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
                start_command
            )
        )

        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                text_handler
            )
        )

        print(
            "✅ Telegram application initialized.",
            flush=True
        )

    except Exception as error:

        print(
            "❌ Telegram application initialization failed:",
            error,
            flush=True
        )

        traceback.print_exc()

        return

    # --------------------------------------------------------
    # COLLECTOR
    # --------------------------------------------------------

    collector_thread = threading.Thread(
        target=start_collector,
        daemon=True
    )

    collector_thread.start()

    print(
        "🟢 Collector thread started.",
        flush=True
    )

    # --------------------------------------------------------
    # TELEGRAM POLLING
    # --------------------------------------------------------

    print(
        "📡 Starting Telegram polling...",
        flush=True
    )

    try:

        application.run_polling(
            drop_pending_updates=True
        )

    except Exception as error:

        print(
            "❌ Telegram polling failed.",
            flush=True
        )

        print(
            f"Type: {type(error).__name__}",
            flush=True
        )

        print(
            f"Message: {error}",
            flush=True
        )

        traceback.print_exc()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
