"""
Authorization System - Manage authorized users for /refund command
"""
import logging
from config import OWNER_ID, AUTHORIZED_USERS

logger = logging.getLogger(__name__)


class AuthSystem:
    def __init__(self):
        self.authorized_users = AUTHORIZED_USERS
        logger.info("Authorization system initialized")
    
    def authorize_user(self, user_id):
        """Add user to authorized list"""
        self.authorized_users.add(user_id)
        logger.info(f"User {user_id} authorized")
        return True
    
    def deauthorize_user(self, user_id):
        """Remove user from authorized list"""
        if user_id in self.authorized_users:
            self.authorized_users.remove(user_id)
            logger.info(f"User {user_id} deauthorized")
            return True
        return False
    
    def is_authorized(self, user_id):
        """Check if user is authorized"""
        return user_id in self.authorized_users or user_id == OWNER_ID
    
    def is_owner(self, user_id):
        """Check if user is the bot owner"""
        return user_id == OWNER_ID
    
    def get_authorized_users(self):
        """Get list of authorized users"""
        return list(self.authorized_users)
    
    def get_help_message(self, user_id):
        """Get help message based on user authorization"""
        if self.is_owner(user_id):
            return """
🤖 *P2P Middleman Bot - Owner Commands*

*Deal Management:*
/deal @username - Start a new deal
/status - Check bot status

*Authorization:*
/auth <user_id> - Authorize user for refunds
/deauth <user_id> - Remove user authorization
/listauth - List authorized users

*Transaction Commands:*
/refund - Refund to seller (in deal room)
/balance - Check admin wallet balances

*Help:*
/help - Show this message
            """
        elif self.is_authorized(user_id):
            return """
🤖 *P2P Middleman Bot - Authorized User*

*Deal Management:*
/deal @username - Start a new deal
/status - Check bot status

*Transaction Commands:*
/refund - Refund to seller (in deal room)

*Help:*
/help - Show this message
            """
        else:
            return """
🤖 *P2P Middleman Bot*

*Available Commands:*
/deal @username - Start a new deal
/status - Check bot status
/help - Show this message

*Note:* You are not authorized for refund operations.
Contact the bot owner for authorization.
            """


# Global auth system instance
auth_system = AuthSystem()
