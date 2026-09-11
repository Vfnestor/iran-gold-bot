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


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Iran Gold AI Bot is running.")

    def log_message(self, format, *args):
        return


def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"🌐 Health server running on port {PORT}")
    server.serve_forever()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🟡 سلام!\n\n"
        "من Iran Gold AI هستم.\n"
        "به‌زودی تحلیل بازار طلای ایران را برایت انجام می‌دهم."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 دستورات فعلی:\n\n"
        "/start - شروع ربات\n"
        "/help - راهنما\n"
        "/price - قیمت طلای ۱۸ عیار"
    )


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = get_gold_18k()

        price = data["price"]

        await update.message.reply_text(
            "🟡 طلای ۱۸ عیار\n\n"
            f"💰 قیمت: {price:,} ریال\n"
            f"📡 منبع: {data['source']}"
        )

        except Exception as error:
        except(f"TGJU error: {error}")

           awaitt update.message.reply_text(
               f"❌ خطای دریافت قیمت:\n\n"
               ff"{type(error).__name__}: {error}"
         )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured.")

    health_thread = threading.Thread(
        target=run_health_server,
        daemon=True,
    )
    health_thread.start()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("price", price_command)
    )

    print("🤖 Iran Gold AI Bot is running...")

    application.run_polling()


if __name__ == "__main__":
    main()
