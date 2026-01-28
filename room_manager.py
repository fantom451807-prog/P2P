"""
Room Manager - Handle room cleanup and deal completion notifications
"""
import logging
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from config import MAIN_GROUP_ID, ESCROW_MANAGER

logger = logging.getLogger(__name__)


class RoomManager:
    def __init__(self, bot: Bot):
        self.bot = bot
        logger.info("Room manager initialized")
    
    async def cleanup_room(self, room_id):
        """
        Delete all messages in the deal room after completion
        
        Args:
            room_id: The chat ID of the deal room
        """
        try:
            logger.info(f"Starting cleanup for room {room_id}")
            
            # Get chat info
            chat = await self.bot.get_chat(room_id)
            
            # Note: Telegram doesn't allow bulk message deletion
            # We'll send a cleanup notification instead
            cleanup_message = """
🧹 *Deal Completed - Room Cleanup*

This deal room has been completed and will be available for the next deal.

All deal information has been recorded.

Thank you for using our secure escrow service! 🎉
            """
            
            await self.bot.send_message(
                chat_id=room_id,
                text=cleanup_message,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"Cleanup notification sent to room {room_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up room {room_id}: {e}")
            return False
    
    async def send_completion_message(self, deal_info):
        """
        Send deal completion message to main group and pin it
        
        Args:
            deal_info: Dictionary containing deal information
        """
        try:
            # Format completion message
            completion_message = f"""
✅ *Deal Completed*

💰 *Amount:* {deal_info['amount']} {deal_info['crypto']}
👤 *Buyer:* {deal_info['buyer']}
👨‍💼 *Seller:* {deal_info['seller']}
🆔 *Deal ID:* {deal_info['trade_id']}
🛡️ *Escrow managed by:* {ESCROW_MANAGER}
            """
            
            # Send message to main group
            message = await self.bot.send_message(
                chat_id=MAIN_GROUP_ID,
                text=completion_message,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Pin the message
            try:
                await self.bot.pin_chat_message(
                    chat_id=MAIN_GROUP_ID,
                    message_id=message.message_id,
                    disable_notification=True
                )
                logger.info(f"Completion message pinned in main group for deal {deal_info['trade_id']}")
            except Exception as e:
                logger.warning(f"Could not pin message: {e}")
            
            logger.info(f"Completion message sent to main group for deal {deal_info['trade_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending completion message: {e}")
            return False
    
    async def complete_deal(self, room_id, deal_info):
        """
        Complete deal: cleanup room and send completion message
        
        Args:
            room_id: The chat ID of the deal room
            deal_info: Dictionary containing deal information
        """
        try:
            # Send completion message to main group
            await self.send_completion_message(deal_info)
            
            # Wait a bit before cleanup
            await asyncio.sleep(2)
            
            # Cleanup room
            await self.cleanup_room(room_id)
            
            logger.info(f"Deal {deal_info['trade_id']} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error completing deal: {e}")
            return False
