"""
Configuration file for P2P Middleman Bot
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Credentials
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
OWNER_ID = 0000000  # Your Telegram user ID
API_ID = "YOUR_API_ID"
API_HASH = "YOUR_API_HASH"

# Blockchain Configuration (from .env)
ADMIN_WALLET_ADDRESS = os.getenv("ADMIN_WALLET_ADDRESS")
ADMIN_WALLET_PRIVATE_KEY = os.getenv("ADMIN_WALLET_PRIVATE_KEY")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
BSC_RPC_URL = os.getenv("BSC_RPC_URL")
CONFIRMATION_BLOCKS = int(os.getenv("CONFIRMATION_BLOCKS", 15))
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", 15))
MAX_GAS_PRICE = int(os.getenv("MAX_GAS_PRICE", 10))

# Fee Configuration
DEFAULT_FEE = 0.25  # 0.25%
ZERO_FEE_USERNAME = "@USDTP2PMRKT"
ESCROW_MANAGER = "@USDTP2PMRKT"

# Security Configuration
SECURITY_COOLDOWN_MINUTES = 10  # 10-minute cooldown before release
MIN_CONFIRMATIONS = 15  # Minimum block confirmations

# Room Pool Configuration
# Add your 15-20 group chat IDs here
ROOM_POOL = [
    -1001234567890,  # Deal room 1
    -1001234567891,  # Deal room 2
    -1001234567892,  # Deal room 3
    # Add more group IDs as you create more deal rooms (15-20 total recommended)
]

# Main group where deals are initiated
MAIN_GROUP_ID = -1001234567890  # Your main group ID

# Supported Cryptocurrencies (BEP20/BSC ONLY)
SUPPORTED_CRYPTOS = ["USDT", "USDC"]

# Blockchain Networks (BEP20/BSC ONLY)
BLOCKCHAINS = {
    "USDT": ["BEP20"],
    "USDC": ["BEP20"]
}

# Token Contract Addresses on BSC
TOKEN_CONTRACTS = {
    "USDT": "0x55d398326f99059fF775485246999027B3197955",  # BSC USDT
    "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"   # BSC USDC
}

# Authorized Users (can use /refund command)
AUTHORIZED_USERS = set()  # Will be populated via /auth command

# Messages Configuration
WELCOME_MESSAGE = """
🤖 *P2P Middleman Bot*

Welcome! I help facilitate secure P2P trades.

📝 *Commands:*
/deal @username - Start a new deal
/help - Show help information
/status - Check bot status
"""

DISCLAIMER_MESSAGE = """
⚠️ *P2P Deal Disclaimer* ⚠️

• Always verify the admin wallet before sending any funds.
• Confirm @pool is present in both the deal room & the main group.
• ❌ Never engage in direct or outside-room deals.
• 💬 Share all details only within this deal room.
"""

ROLE_SELECTION_MESSAGE = """
📋 *Step 1 - Select Roles*

⚠️ Choose roles accordingly

As release & refund happen according to roles

*Refund goes to seller & release to buyer*
"""
