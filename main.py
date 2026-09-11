import os
import threading

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from http.server import BaseHTTPRequestHandler, HTTPServer

from data.collectors.tgju import get_gold_18k
from database import (
    init_db,
    save_price,
    get_latest_prices,
)


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))


# ==========================================
# Render Health Server
# ==========================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

        self.wfile.write(
            b"Iran Gold AI Bot is running."
        )

    def log_message(self, format, *args):
        return


def run_health_server():

    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    print(
        f"🌐 Health server running on port {PORT}"
    )

    server.serve_forever()


# ==========================================
# Telegram /start
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🟡 سلام!\n\n"
        "من Iran Gold AI هستم.\n"
        "به‌زودی تحلیل بازار طلای ایران را برایت انجام می‌دهم."
    )


# ==========================================
# Telegram /help
# ==========================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "📌 دستورات فعلی:\n\n"
        "/start - شروع ربات\n"
        "/help - راهنما\n"
        "/price - قیمت طلای ۱۸ عیار\n"
        "/history - تاریخچه قیمت‌ها"
    )


# ==========================================
# Telegram /price
# ==========================================

async def price_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        # دریافت قیمت از TGJU
        data = get_gold_18k()

        # ذخیره قیمت در دیتابیس
        save_price(data)

        price = data["price"]

        await update.message.reply_text(
            "🟡 طلای ۱۸ عیار\n\n"
            f"💰 قیمت: {price:,} ریال\n"
            f"📡 منبع: {data['source']}"
        )

    except Exception as error:

        print(
            f"TGJU error: {error}"
        )

        await update.message.reply_text(
            "❌ خطای دریافت قیمت:\n\n"
            f"{type(error).__name__}: {error}"
        )


# ==========================================
# Telegram /history
# ==========================================

async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        # دریافت آخرین ۱۰ رکورد
        rows = get_latest_prices(10)

        if not rows:

            await update.message.reply_text(
                "📭 هنوز هیچ قیمتی در دیتابیس ذخیره نشده است."
            )

            return

        message = (
            "📊 آخرین قیمت‌های ثبت‌شده\n\n"
        )

        for index, row in enumerate(
            rows,
            start=1
        ):

            price, currency, source, timestamp = row

            message += (
                f"{index}. 💰 {price:,} {currency}\n"
                f"   📡 {source}\n"
                f"   🕐 {timestamp}\n\n"
            )

        await update.message.reply_text(
            message
        )

    except Exception as error:

        print(
            f"History error: {error}"
        )

        await update.message.reply_text(
            "❌ خطا در خواندن تاریخچه:\n\n"
            f"{type(error).__name__}: {error}"
        )


# ==========================================
# Main
# ==========================================

def main():

    # بررسی Token
    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is not configured."
        )

    # ساخت دیتابیس و جدول
    init_db()

    # اجرای Health Server برای Render
    health_thread = threading.Thread(
        target=run_health_server,
        daemon=True
    )

    health_thread.start()

    # ساخت Telegram Application
    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ======================================
    # Command Handlers
    # ======================================

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

    print(
        "🤖 Iran Gold AI Bot is running..."
    )

    # اجرای Telegram Bot
    application.run_polling()


# ==========================================
# Entry Point
# ==========================================

if __name__ == "__main__":
    main()
