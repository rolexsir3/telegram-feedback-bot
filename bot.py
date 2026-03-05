import logging
from threading import Thread
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import BOT_TOKEN
from bot.handlers import (
    start, help_command, handle_user_message,
    stats, broadcast, ban_user_cmd, unban_user_cmd
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Health check server for Koyeb
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "Bot is alive!", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

def main():
    Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("ban", ban_user_cmd))
    app.add_handler(CommandHandler("unban", unban_user_cmd))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_user_message))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
