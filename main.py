import os
import threading

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

from database import (
    init_db,
    save_price,
    get_latest_prices,
)

from candle_engine import build_1m_candle


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

PORT = int(
    os.getenv("PORT", "10000")
)


# ============================================================
# MAIN KEYBOARD
# ============================================================

def get_main_keyboard():

    keyboard = [
        [
            KeyboardButton("🟡 قیمت لحظه‌ای"),
            KeyboardButton("📊 تاریخچه"),
        ],
        [
            KeyboardButton("🕯️ کندل ۱ دقیقه‌ای"),
            KeyboardButton("📡 وضعیت سیستم"),
        ],
        [
            KeyboardButton("🔄 بروزرسانی"),
            KeyboardButton("ℹ️ راهنما"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# ============================================================
# HEALTH SERVER
# ============================================================

class HealthHandler(
    BaseHTTPRequestHandler
):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain"
        )

        self.end_headers()

        self.wfile.write(
            b"Iran Gold AI Bot is running."
        )

    def log_message(
        self,
        format,
        *args
    ):

        return


def run_health_server():

    try:

        server = HTTPServer(
            (
                "0.0.0.0",
                PORT
            ),
            HealthHandler
        )

        print(
            f"🌐 HEALTH: Server running on port {PORT}",
            flush=True
        )

        server.serve_forever()

    except Exception as error:

        print(
            "❌ HEALTH SERVER ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True
        )


# ============================================================
# TELEGRAM COMMANDS
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "📨 TELEGRAM: /start received",
        flush=True
    )

    await update.message.reply_text(

        "🟡 سلام!\n\n"
        "من Iran Gold AI هستم.\n\n"
        "📊 سیستم جمع‌آوری قیمت طلای ایران فعال است.\n\n"
        "📡 داده‌ها به صورت خودکار "
        "جمع‌آوری و ذخیره می‌شوند.\n\n"
        "👇 از منوی زیر استفاده کن.",

        reply_markup=get_main_keyboard()
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "📨 TELEGRAM: /help received",
        flush=True
    )

    await update.message.reply_text(

        "ℹ️ راهنمای Iran Gold AI\n\n"

        "🟡 قیمت لحظه‌ای\n"
        "آخرین قیمت طلای ۱۸ عیار\n\n"

        "📊 تاریخچه\n"
        "آخرین قیمت‌های ذخیره‌شده\n\n"

        "🕯️ کندل ۱ دقیقه‌ای\n"
        "آخرین کندل یک دقیقه‌ای\n\n"

        "📡 وضعیت سیستم\n"
        "وضعیت جمع‌آوری و دیتابیس\n\n"

        "🔄 بروزرسانی\n"
        "دریافت دستی قیمت جدید\n\n"

        "🔮 مراحل بعدی پروژه:\n"
        "• کندل‌های چندبازه‌ای\n"
        "• RSI\n"
        "• MACD\n"
        "• حمایت و مقاومت\n"
        "• روند بازار\n"
        "• مناطق احتمالی خرید\n"
        "• اهداف قیمتی\n"
        "• بک‌تست\n"
        "• تحلیل چندافقی",

        reply_markup=get_main_keyboard()
    )


async def price_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        print(
            "👤 TELEGRAM: Price requested",
            flush=True
        )

        data = get_gold_18k()

        save_price(data)

        print(
            "💾 TELEGRAM: Price saved.",
            flush=True
        )

        try:

            candle = build_1m_candle(
                symbol=data["symbol"]
            )

            if candle:

                print(
                    "🕯️ TELEGRAM: "
                    "1M candle updated.",
                    flush=True
                )

        except Exception as error:

            print(
                "❌ TELEGRAM CANDLE ERROR: "
                f"{type(error).__name__}: "
                f"{error}",
                flush=True
            )

        price = data["price"]

        await update.message.reply_text(

            "🟡 طلای ۱۸ عیار\n\n"

            f"💰 قیمت: "
            f"{price:,} ریال\n"

            f"📡 منبع: "
            f"{data['source']}\n"

            f"🕐 زمان دریافت: "
            f"{data['timestamp']}",

            reply_markup=get_main_keyboard()
        )

    except Exception as error:

        print(
            "❌ TELEGRAM PRICE ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True
        )

        await update.message.reply_text(

            "❌ در دریافت قیمت مشکلی پیش آمد.\n\n"
            f"{type(error).__name__}: {error}",

            reply_markup=get_main_keyboard()
        )


async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        print(
            "📊 TELEGRAM: History requested",
            flush=True
        )

        rows = get_latest_prices(10)

        if not rows:

            await update.message.reply_text(

                "📭 هنوز هیچ قیمتی "
                "در دیتابیس ذخیره نشده است.",

                reply_markup=get_main_keyboard()
            )

            return

        message = (
            "📊 آخرین قیمت‌های ثبت‌شده\n\n"
        )

        for index, row in enumerate(
            rows,
            start=1
        ):

            price = row[0]

            currency = row[1]

            source = row[2]

            timestamp = row[3]

            message += (

                f"{index}. "
                f"💰 {price:,} {currency}\n"

                f"   📡 {source}\n"

                f"   🕐 {timestamp}\n\n"
            )

        await update.message.reply_text(

            message,

            reply_markup=get_main_keyboard()
        )

    except Exception as error:

        print(
            "❌ HISTORY ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True
        )

        await update.message.reply_text(

            "❌ خطا در خواندن تاریخچه:\n\n"
            f"{type(error).__name__}: {error}",

            reply_markup=get_main_keyboard()
        )


async def candle_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        print(
            "🕯️ TELEGRAM: Candle requested",
            flush=True
        )

        candle = build_1m_candle(
            symbol="gold_18k"
        )

        if not candle:

            await update.message.reply_text(

                "🕯️ هنوز اطلاعات کافی "
                "برای ساخت کندل ۱ دقیقه‌ای وجود ندارد.",

                reply_markup=get_main_keyboard()
            )

            return

        message = (

            "🕯️ آخرین کندل ۱ دقیقه‌ای\n\n"

            f"🕐 زمان: "
            f"{candle['timestamp']}\n\n"

            f"🟢 Open: "
            f"{candle['open']:,} ریال\n"

            f"🔺 High: "
            f"{candle['high']:,} ریال\n"

            f"🔻 Low: "
            f"{candle['low']:,} ریال\n"

            f"🔴 Close: "
            f"{candle['close']:,} ریال\n\n"

            f"📊 Samples: "
            f"{candle['volume']}"
        )

        await update.message.reply_text(

            message,

            reply_markup=get_main_keyboard()
        )

    except Exception as error:

        print(
            "❌ CANDLE COMMAND ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True
        )

        await update.message.reply_text(

            "❌ خطا در دریافت کندل:\n\n"
            f"{type(error).__name__}: {error}",

            reply_markup=get_main_keyboard()
        )


async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        print(
            "📡 TELEGRAM: Status requested",
            flush=True
        )

        rows = get_latest_prices(1)

        if rows:

            latest = rows[0]

            price = latest[0]

            currency = latest[1]

            source = latest[2]

            timestamp = latest[3]

            database_status = "🟢 فعال"

            price_status = (
                f"💰 {price:,} {currency}"
            )

            source_status = (
                f"📡 {source}"
            )

            time_status = (
                f"🕐 {timestamp}"
            )

        else:

            database_status = "🟡 فعال ولی خالی"

            price_status = (
                "💰 هنوز داده‌ای ثبت نشده"
            )

            source_status = (
                "📡 ---"
            )

            time_status = (
                "🕐 ---"
            )

        await update.message.reply_text(

            "📡 وضعیت Iran Gold AI\n\n"

            "🤖 Telegram Bot: 🟢 فعال\n"

            f"🗄️ Database: "
            f"{database_status}\n"

            f"📥 آخرین قیمت: "
            f"{price_status}\n"

            f"{source_status}\n"

            f"{time_status}\n\n"

            "🕯️ Candle Engine: 🟢 فعال\n"

            "📊 Collector: 🟢 فعال",

            reply_markup=get_main_keyboard()
        )

    except Exception as error:

        print(
            "❌ STATUS ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True
        )

        await update.message.reply_text(

            "❌ خطا در بررسی وضعیت سیستم:\n\n"
            f"{type(error).__name__}: {error}",

            reply_markup=get_main_keyboard()
        )


# ============================================================
# MENU HANDLER
# ============================================================

async def menu_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text

    print(
        f"🔘 TELEGRAM BUTTON: {text}",
        flush=True
    )

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

    elif text == "🕯️ کندل ۱ دقیقه‌ای":

        await candle_command(
            update,
            context
        )

    elif text == "📡 وضعیت سیستم":

        await status_command(
            update,
            context
        )

    elif text == "🔄 بروزرسانی":

        await price_command(
            update,
            context
        )

    elif text == "ℹ️ راهنما":

        await help_command(
            update,
            context
        )

    else:

        await update.message.reply_text(

            "🤔 این گزینه را متوجه نشدم.\n"
            "لطفاً از دکمه‌های منو استفاده کن.",

            reply_markup=get_main_keyboard()
        )


# ============================================================
# TELEGRAM ERROR HANDLER
# ============================================================

async def telegram_error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    error = context.error

    print(
        "🚨 TELEGRAM ERROR",
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

    print(
        "--------------------------------",
        flush=True
    )


# ============================================================
# APPLICATION STARTUP
# ============================================================

def main():

    print(
        "========================================",
        flush=True
    )

    print(
        "🚀 IRAN GOLD AI BOT STARTING",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    # --------------------------------------------------------
    # TOKEN CHECK
    # --------------------------------------------------------

    if not BOT_TOKEN:

        print(
            "❌ STARTUP ERROR: BOT_TOKEN is missing.",
            flush=True
        )

        raise RuntimeError(
            "BOT_TOKEN is not configured."
        )

    print(
        "🔐 BOT_TOKEN: configured",
        flush=True
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    try:

        init_db()

        print(
            "🗄️ DATABASE: initialized successfully",
            flush=True
        )

    except Exception as error:

        print(
            "❌ DATABASE INIT ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True
        )

        raise

    # --------------------------------------------------------
    # HEALTH SERVER
    # --------------------------------------------------------

    health_thread = threading.Thread(
        target=run_health_server,
        daemon=True
    )

    health_thread.start()

    print(
        "🌐 HEALTH: thread started",
        flush=True
    )

    # --------------------------------------------------------
    # TELEGRAM APPLICATION
    # --------------------------------------------------------

    try:

        print(
            "📡 TELEGRAM: creating application...",
            flush=True
        )

        application = (
            Application
            .builder()
            .token(BOT_TOKEN)
            .build()
        )

        print(
            "📡 TELEGRAM: application created",
            flush=True
        )

    except Exception as error:

        print(
            "❌ TELEGRAM APPLICATION ERROR: "
            f"{type(error).__name__}: {error}",
            flush=True
        )

        raise

    # --------------------------------------------------------
    # HANDLERS
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "price",
            price_command
        )
    )

    application.add_handler(
        CommandHandler(
            "history",
            history_command
        )
    )

    application.add_handler(
        CommandHandler(
            "candle",
            candle_command
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            status_command
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            menu_handler
        )
    )

    application.add_error_handler(
        telegram_error_handler
    )

    print(
        "🧩 TELEGRAM: handlers registered",
        flush=True
    )

    # --------------------------------------------------------
    # COLLECTOR
    # --------------------------------------------------------

    collector_thread = threading.Thread(
        target=run_collector,
        daemon=True
    )

    collector_thread.start()

    print(
        "📡 COLLECTOR: thread started",
        flush=True
    )

    # --------------------------------------------------------
    # TELEGRAM POLLING
    # --------------------------------------------------------

    print(
        "========================================",
        flush=True
    )

    print(
        "🤖 Iran Gold AI Bot is running...",
        flush=True
    )

    print(
        "📡 TELEGRAM: starting polling...",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    try:

        application.run_polling(
            drop_pending_updates=True
        )

    except Exception as error:

        print(
            "🚨 POLLING ERROR",
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

        print(
            "========================================",
            flush=True
        )

        raise


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
