"""
P2P Middleman Telegram Bot - Main Entry Point
Complete version with blockchain integration
"""

import logging
import random
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,    
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

from config import *
# Use Web3 direct blockchain reading (NO API needed!)
from blockchain_monitor_web3 import monitor
from transaction_handler import tx_handler
from auth_system import auth_system
from room_manager import RoomManager

WAITING_AMOUNT, WAITING_RATE, WAITING_PAYMENT_METHOD, WAITING_BUYER_ADDRESS, WAITING_SELLER_ADDRESS = range(5)

active_deals = {}
room_status = {}
user_states = {}


class Deal:
    def __init__(self, initiator, counterparty, room_id, main_group_id):
        self.trade_id = f"#P2PMMX{random.randint(1000, 9999)}"
        self.initiator = initiator
        self.counterparty = counterparty
        self.room_id = room_id
        self.main_group_id = main_group_id
        self.buyer = None
        self.seller = None
        self.buyer_id = None
        self.seller_id = None
        self.crypto = None
        self.blockchain = "BEP20"
        self.amount = None
        self.rate = None
        self.payment_method = None
        self.buyer_address = None
        self.seller_address = None
        self.fee_percentage = DEFAULT_FEE
        self.created_at = datetime.now()
        self.payment_detected_at = None
        self.status = "created"
        self.user_bios = {}
        self.tx_hash = None
        self.members_joined = []
        self.setup_sent = False
        self.invite_link = None
        self.waiting_for_buyer_address = False
        self.waiting_for_seller_address = False
    
    def can_release(self):
        if not self.payment_detected_at:
            return False
        elapsed = datetime.now() - self.payment_detected_at
        return elapsed >= timedelta(minutes=SECURITY_COOLDOWN_MINUTES)
    
    def time_until_release(self):
        if not self.payment_detected_at:
            return None
        elapsed = datetime.now() - self.payment_detected_at
        remaining = timedelta(minutes=SECURITY_COOLDOWN_MINUTES) - elapsed
        if remaining.total_seconds() <= 0:
            return None
        minutes = int(remaining.total_seconds() // 60)
        seconds = int(remaining.total_seconds() % 60)
        return f"{minutes} min(s) {seconds} sec(s)"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.chat.type == "private":
        help_msg = auth_system.get_help_message(user_id)
        await update.message.reply_text(help_msg, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(
            "🤖 *P2P Middleman Bot*\n\nWelcome! Secure P2P trades.\n\n"
            "/deal @username - Start deal\n/help - Help\n/status - Status",
            parse_mode=ParseMode.MARKDOWN
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.chat.type == "private":
        help_msg = auth_system.get_help_message(user_id)
        await update.message.reply_text(help_msg, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(
            "🤖 *P2P Bot Help*\n\n1️⃣ /deal @username\n2️⃣ Join room\n3️⃣ Select roles\n"
            "4️⃣ Choose crypto\n5️⃣ Enter details\n6️⃣ Seller sends to admin\n"
            "7️⃣ Bot detects payment\n8️⃣ 10-min cooldown\n9️⃣ /release\n🔟 Auto-send to buyer",
            parse_mode=ParseMode.MARKDOWN
        )


async def deal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /deal @username")
        return
    
    initiator = update.message.from_user
    counterparty = context.args[0].lstrip('@')
    
    available_room = next((r for r in ROOM_POOL if not room_status.get(r, False)), None)
    if not available_room:
        await update.message.reply_text("❌ No rooms available.")
        return
    
    deal = Deal(initiator, counterparty, available_room, update.message.chat_id)
    room_status[available_room] = True
    active_deals[available_room] = deal
    
    try:
        invite_link = await context.bot.export_chat_invite_link(available_room)
        deal.invite_link = invite_link  # Store invite link
    except:
        invite_link = "Error"
    
    await update.message.reply_text(
        f"🏠 *Deal Room Created!*\n\n🔗 {invite_link}\n\n"
        f"👥 @{initiator.username or initiator.first_name} & @{counterparty}\n"
        f"💰 Fee: {deal.fee_percentage}%",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


async def handle_member_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in active_deals:
        return
    
    deal = active_deals[chat_id]
    
    # Track each member that joins
    for member in update.message.new_chat_members:
        if member.id not in deal.members_joined:
            deal.members_joined.append(member.id)
            username = f"@{member.username}" if member.username else member.first_name
            await update.message.reply_text(f"✅ {username} joined.")
            
            try:
                chat_member = await context.bot.get_chat(member.id)
                bio = chat_member.bio if hasattr(chat_member, 'bio') and chat_member.bio else ""
                deal.user_bios[member.id] = bio
            except:
                pass
    
    # Only send disclaimer + role selection ONCE when BOTH members have joined
    if len(deal.members_joined) >= 2 and not deal.setup_sent:
        deal.setup_sent = True
        
        # Check for zero fee
        if len(deal.user_bios) >= 2:
            all_have = all(ZERO_FEE_USERNAME in bio for bio in deal.user_bios.values())
            deal.fee_percentage = 0 if all_have else DEFAULT_FEE
        
        # Revoke invite link - PROPERLY
        if deal.invite_link:
            try:
                await context.bot.revoke_chat_invite_link(chat_id, deal.invite_link)
                logger.info(f"✅ Invite link revoked for room {chat_id}")
            except Exception as e:
                logger.error(f"Failed to revoke invite link: {e}")
        
        # Send disclaimer
        await context.bot.send_message(
            chat_id,
            "⚠️ Disclaimer\n\n• Verify admin wallet\n• No outside deals\n• Share in room only"
        )
        
        # Send role selection
        keyboard = [[
            InlineKeyboardButton("👤 Buyer", callback_data=f"role_buyer_{chat_id}"),
            InlineKeyboardButton("💼 Seller", callback_data=f"role_seller_{chat_id}")
        ]]
        await context.bot.send_message(
            chat_id,
            "📋 Step 1 - Select Roles\n\n⚠️ Choose carefully\nRefund → Seller | Release → Buyer",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def handle_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    role, chat_id = query.data.split('_')[1], int(query.data.split('_')[2])
    if chat_id not in active_deals:
        await query.edit_message_text("❌ Deal not found.")
        return
    
    deal = active_deals[chat_id]
    user = query.from_user
    username = f"@{user.username}" if user.username else user.first_name
    
    # Store who clicked the button
    if role == "buyer":
        deal.buyer = username
        deal.buyer_id = user.id
        # The other person is the seller - find their ID from members_joined
        for member_id in deal.members_joined:
            if member_id != user.id:
                deal.seller_id = member_id
                # Get seller username from initiator/counterparty
                if deal.initiator.id == member_id:
                    deal.seller = f"@{deal.initiator.username}" if deal.initiator.username else deal.initiator.first_name
                else:
                    deal.seller = f"@{deal.counterparty}"
                break
    else:  # seller
        deal.seller = username
        deal.seller_id = user.id
        # The other person is the buyer - find their ID from members_joined
        for member_id in deal.members_joined:
            if member_id != user.id:
                deal.buyer_id = member_id
                # Get buyer username from initiator/counterparty
                if deal.initiator.id == member_id:
                    deal.buyer = f"@{deal.initiator.username}" if deal.initiator.username else deal.initiator.first_name
                else:
                    deal.buyer = f"@{deal.counterparty}"
                break
    
    await query.edit_message_text(
        f"📋 *Roles*\n\n✅ {deal.buyer} - BUYER\n✅ {deal.seller} - SELLER",
        parse_mode=ParseMode.MARKDOWN
    )
    
    keyboard = [[
        InlineKeyboardButton("USDT", callback_data=f"crypto_usdt_{chat_id}"),
        InlineKeyboardButton("USDC", callback_data=f"crypto_usdc_{chat_id}")
    ]]
    await context.bot.send_message(
        chat_id,
        "🪙 *Step 2 - Select Coin* (BEP20/BSC)",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_crypto_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    crypto, chat_id = query.data.split('_')[1].upper(), int(query.data.split('_')[2])
    if chat_id not in active_deals:
        await query.edit_message_text("❌ Deal not found.")
        return
    
    active_deals[chat_id].crypto = crypto
    await query.edit_message_text(f"🪙 *Coin*\n\n✅ {crypto} (BEP20/BSC)", parse_mode=ParseMode.MARKDOWN)
    
    await context.bot.send_message(
        chat_id,
        f"💰 *Step 3 - Enter {crypto} Amount*\n\nChain: BEP20\nExample: 1000",
        parse_mode=ParseMode.MARKDOWN
    )
    user_states[chat_id] = WAITING_AMOUNT


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in active_deals:
        return
    
    deal = active_deals[chat_id]
    state = user_states.get(chat_id)
    text = update.message.text.strip()
    
    if state == WAITING_AMOUNT:
        try:
            deal.amount = float(text)
            user_states[chat_id] = WAITING_RATE
            await update.message.reply_text(f"💵 *Step 4 - Rate per {deal.crypto}*\nExample: 89.5", parse_mode=ParseMode.MARKDOWN)
        except:
            await update.message.reply_text("❌ Invalid amount.")
    
    elif state == WAITING_RATE:
        try:
            deal.rate = float(text)
            user_states[chat_id] = WAITING_PAYMENT_METHOD
            await update.message.reply_text("💳 *Step 5 - Payment method*\nExamples: UPI, CASH", parse_mode=ParseMode.MARKDOWN)
        except:
            await update.message.reply_text("❌ Invalid rate.")
    
    elif state == WAITING_PAYMENT_METHOD:
        deal.payment_method = text.upper()
        user_states[chat_id] = WAITING_BUYER_ADDRESS
        deal.waiting_for_buyer_address = True
        await update.message.reply_text(
            f"Step 6 - {deal.buyer}, BEP20 address\nFormat: 0x... (42 chars)"
        )
    
    elif state == WAITING_BUYER_ADDRESS:
        # Verify it's the buyer sending the address
        user_id = update.message.from_user.id
        if user_id != deal.buyer_id:
            await update.message.reply_text(f"❌ Only {deal.buyer} can provide buyer address.")
            return
        
        if not text.startswith("0x") or len(text) != 42:
            await update.message.reply_text("❌ Invalid address format.")
            return
        
        deal.buyer_address = text
        deal.waiting_for_buyer_address = False
        user_states[chat_id] = WAITING_SELLER_ADDRESS
        deal.waiting_for_seller_address = True
        await update.message.reply_text(
            f"Step 7 - {deal.seller}, BEP20 address\nFormat: 0x... (42 chars)"
        )
    
    elif state == WAITING_SELLER_ADDRESS:
        # Verify it's the seller sending the address
        user_id = update.message.from_user.id
        if user_id != deal.seller_id:
            await update.message.reply_text(f"❌ Only {deal.seller} can provide seller address.")
            return
        
        if not text.startswith("0x") or len(text) != 42:
            await update.message.reply_text("❌ Invalid address format.")
            return
        
        deal.seller_address = text
        deal.waiting_for_seller_address = False
        user_states[chat_id] = None
        
        await context.bot.send_message(
            chat_id,
            f"📋 *Deal Summary*\n\n• ID: {deal.trade_id}\n• Amount: {deal.amount} {deal.crypto}\n"
            f"• Rate: ₹{deal.rate}\n• Payment: {deal.payment_method}\n\n"
            f"👤 Buyer: {deal.buyer}\n`{deal.buyer_address}`\n\n"
            f"👨‍💼 Seller: {deal.seller}\n`{deal.seller_address}`\n\n"
            f"🏦 *Admin Wallet:*\n`{ADMIN_WALLET_ADDRESS}`\n\n"
            f"⚠️ {deal.seller}, send {deal.amount} {deal.crypto} to admin wallet\n\n🔍 Monitoring...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Start monitoring with detailed logging
        monitor_info = {
            'crypto': deal.crypto,
            'amount': deal.amount,
            'seller_address': deal.seller_address,
            'room_id': chat_id
        }
        logger.info(f"🔍 Starting monitor for {deal.trade_id}")
        logger.info(f"   Crypto: {deal.crypto}")
        logger.info(f"   Amount: {deal.amount}")
        logger.info(f"   Seller: {deal.seller_address}")
        logger.info(f"   Admin: {ADMIN_WALLET_ADDRESS}")
        
        monitor.start_monitoring(deal.trade_id, monitor_info)
        logger.info(f"✅ Monitor started for {deal.trade_id}")


async def check_payments(context: ContextTypes.DEFAULT_TYPE):
    """Check for new payments - called by job queue"""
    try:
        logger.info(f"🔍 Checking payments... (Monitoring {len(monitor.monitored_deals)} deals)")
        detected = await monitor.check_transactions()
        logger.info(f"   Found {len(detected)} payments")
        
        for payment in detected:
            deal = next((d for d in active_deals.values() if d.trade_id == payment['deal_id']), None)
            if deal:
                chat_id = deal.room_id
                deal.status = "funded"
                deal.payment_detected_at = datetime.now()
                deal.tx_hash = payment['tx_hash']
                
                await context.bot.send_message(
                    chat_id,
                    f"🟢 *Exact {payment['token']} found*\n\n"
                    f"💰 Amount: {payment['amount']} {payment['token']}\n"
                    f"📤 From: `{payment['from_address']}`\n"
                    f"📥 To: `{ADMIN_WALLET_ADDRESS}`\n"
                    f"🔗 [View TX]({monitor.get_transaction_link(payment['tx_hash'])})\n\n"
                    f"✅ *Payment Received!*\n\nUse /release After Fund Transfer to Seller\n\n"
                    f"🕐 *Security Cooldown:* {SECURITY_COOLDOWN_MINUTES} minutes",
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
    except Exception as e:
        logger.error(f"Payment check error: {e}")


async def release_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    
    if chat_id not in active_deals:
        await update.message.reply_text("❌ Use in deal room only.")
        return
    
    deal = active_deals[chat_id]
    
    if user_id != deal.seller_id:
        await update.message.reply_text(f"❌ Only {deal.seller} can release.")
        return
    
    if deal.status != "funded":
        await update.message.reply_text("❌ Payment not detected.")
        return
    
    if not deal.can_release():
        await update.message.reply_text(
            f"⏳ *Cooldown*\n\nWait {deal.time_until_release()}",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    keyboard = [[InlineKeyboardButton("✅ Confirm Release", callback_data=f"confirm_release_{chat_id}")]]
    await update.message.reply_text(
        f"🔓 *Release {deal.amount} {deal.crypto}*\n\n"
        f"To: {deal.buyer}\n`{deal.buyer_address}`\n\n⚠️ Cannot undo!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_release_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = int(query.data.split('_')[2])
    if chat_id not in active_deals:
        await query.edit_message_text("❌ Deal not found.")
        return
    
    deal = active_deals[chat_id]
    await query.edit_message_text("⏳ *Processing...*", parse_mode=ParseMode.MARKDOWN)
    
    result = await tx_handler.send_token(deal.buyer_address, deal.amount, deal.crypto)
    
    if result['success']:
        deal.status = "completed"
        await context.bot.send_message(
            chat_id,
            f"🎉 *Complete!* ✅\n\n💰 {result['amount']} {result['token']}\n"
            f"👤 {deal.buyer}\n🔗 [TX]({result['bscscan_link']})",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        
        room_mgr = RoomManager(context.bot)
        await room_mgr.complete_deal(chat_id, {
            'trade_id': deal.trade_id,
            'amount': f"{deal.amount} {deal.crypto}",
            'buyer': deal.buyer,
            'seller': deal.seller
        })
        
        room_status[chat_id] = False
        monitor.stop_monitoring(deal.trade_id)
    else:
        await context.bot.send_message(chat_id, f"❌ Failed: {result['error']}", parse_mode=ParseMode.MARKDOWN)


async def refund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    
    if not auth_system.is_authorized(user_id):
        await update.message.reply_text("❌ Not authorized.")
        return
    
    if chat_id not in active_deals:
        await update.message.reply_text("❌ Use in deal room only.")
        return
    
    deal = active_deals[chat_id]
    if deal.status != "funded":
        await update.message.reply_text("❌ Payment not detected.")
        return
    
    keyboard = [[InlineKeyboardButton("✅ Confirm Refund", callback_data=f"confirm_refund_{chat_id}")]]
    await update.message.reply_text(
        f"🔄 *Refund {deal.amount} {deal.crypto}*\n\n"
        f"To: {deal.seller}\n`{deal.seller_address}`\n\n⚠️ Cannot undo!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_refund_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = int(query.data.split('_')[2])
    if chat_id not in active_deals:
        await query.edit_message_text("❌ Deal not found.")
        return
    
    deal = active_deals[chat_id]
    await query.edit_message_text("⏳ *Processing...*", parse_mode=ParseMode.MARKDOWN)
    
    result = await tx_handler.send_token(deal.seller_address, deal.amount, deal.crypto)
    
    if result['success']:
        await context.bot.send_message(
            chat_id,
            f"🔄 *Refunded!* ✅\n\n💰 {result['amount']} {result['token']}\n"
            f"👨‍💼 {deal.seller}\n🔗 [TX]({result['bscscan_link']})",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        room_status[chat_id] = False
        monitor.stop_monitoring(deal.trade_id)
    else:
        await context.bot.send_message(chat_id, f"❌ Failed: {result['error']}", parse_mode=ParseMode.MARKDOWN)


async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_owner(update.message.from_user.id):
        await update.message.reply_text("❌ Owner only.")
        return
    if update.message.chat.type != "private":
        await update.message.reply_text("❌ DM only.")
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /auth <user_id>")
        return
    try:
        auth_system.authorize_user(int(context.args[0]))
        await update.message.reply_text(f"✅ User {context.args[0]} authorized.")
    except:
        await update.message.reply_text("❌ Invalid user ID.")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_authorized(update.message.from_user.id):
        await update.message.reply_text("❌ Not authorized.")
        return
    
    await update.message.reply_text(
        f"💼 *Balances*\n\n`{ADMIN_WALLET_ADDRESS}`\n\n"
        f"💰 USDT: {tx_handler.get_token_balance('USDT'):.2f}\n"
        f"💰 USDC: {tx_handler.get_token_balance('USDC'):.2f}\n"
        f"⛽ BNB: {tx_handler.get_bnb_balance():.4f}",
        parse_mode=ParseMode.MARKDOWN
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = len([r for r in room_status.values() if r])
    await update.message.reply_text(
        f"📊 *Status*\n\n🏠 Rooms: {len(ROOM_POOL)}\n✅ Available: {len(ROOM_POOL)-active}\n"
        f"🔴 Occupied: {active}\n📝 Deals: {len(active_deals)}",
        parse_mode=ParseMode.MARKDOWN
    )


def main():
    # Build application with job queue enabled
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("deal", deal_command))
    app.add_handler(CommandHandler("release", release_command))
    app.add_handler(CommandHandler("refund", refund_command))
    app.add_handler(CommandHandler("auth", auth_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("status", status_command))
    
    # Add callback handlers
    app.add_handler(CallbackQueryHandler(handle_role_selection, pattern="^role_"))
    app.add_handler(CallbackQueryHandler(handle_crypto_selection, pattern="^crypto_"))
    app.add_handler(CallbackQueryHandler(handle_release_confirmation, pattern="^confirm_release_"))
    app.add_handler(CallbackQueryHandler(handle_refund_confirmation, pattern="^confirm_refund_"))
    
    # Add message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_member_join))
    
    # Start payment monitoring job
    if app.job_queue:
        app.job_queue.run_repeating(check_payments, interval=POLLING_INTERVAL, first=10)
        logger.info("🔍 Blockchain monitor started")
    else:
        logger.warning("⚠️ Job queue not available - payment monitoring disabled")
    
    logger.info("🚀 P2P Middleman Bot started!")
    logger.info(f"📊 Monitoring admin wallet: {ADMIN_WALLET_ADDRESS}")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
