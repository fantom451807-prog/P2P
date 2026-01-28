import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

from config import (
    TELEGRAM_BOT_TOKEN,
    POLLING_INTERVAL
)

from blockchain_monitor_web3 import monitor

# =========================
# Logging
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =========================
# Commands
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 P2P MM Bot is ONLINE\n\nMonitoring blockchain deposits..."
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deals = len(monitor.monitored_deals)
    await update.message.reply_text(
        f"📊 Bot Status\n\nActive deals: {deals}"
    )

# =========================
# Background Job
# =========================
async def check_payments(context: ContextTypes.DEFAULT_TYPE):
    try:
        payments = await monitor.check_transactions()

        if payments:
            for payment in payments:
                logger.info(
                    f"Payment confirmed | Deal {payment['deal_id']} | "
                    f"{payment['amount']} {payment['token']}"
                )

    except Exception as e:
        logger.error(f"Payment check error: {e}")

# =========================
# Setup Handlers
# =========================
def setup_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

# =========================
# MAIN (ANTI-CRASH LOOP)
# =========================
def main():
    while True:
        try:
            logger.info("🚀 Starting bot...")

            app = Application.builder().token(
                TELEGRAM_BOT_TOKEN
            ).build()

            setup_handlers(app)

            if app.job_queue:
                app.job_queue.run_repeating(
                    check_payments,
                    interval=POLLING_INTERVAL,
                    first=10
                )

            app.run_polling(allowed_updates=Update.ALL_TYPES)

        except Exception as e:
            logger.error(f"❌ Bot crashed: {e}")
            logger.info("♻️ Restarting bot in 5 seconds...")
            asyncio.sleep(5)

# =========================
# Entry Point
# =========================
if __name__ == "__main__":
    main()
