"""
Blockchain Monitor - Direct Web3 Reading (NO API NEEDED)
Reads directly from BSC blockchain for instant, unlimited transaction detection
"""

import asyncio
import logging
from datetime import datetime
from web3 import Web3
from web3.exceptions import BlockNotFound
from telegram import Bot

from config import (
    ADMIN_WALLET_ADDRESS,
    BSC_RPC_URL,
    TOKEN_CONTRACTS,
    CONFIRMATION_BLOCKS,
    POLLING_INTERVAL,
    TELEGRAM_BOT_TOKEN,
    GROUP_CHAT_ID
)

logger = logging.getLogger(__name__)

# =========================
# Telegram Bot
# =========================
telegram_bot = Bot(token=TELEGRAM_BOT_TOKEN)

async def send_group_notification(message: str):
    await telegram_bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=message,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# =========================
# Token ABI
# =========================
TOKEN_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]

class BlockchainMonitorWeb3:
    """
    Direct blockchain reading - NO API needed!
    Reads Transfer events directly from BSC blockchain
    """

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
        self.monitored_deals = {}
        self.processed_txs = set()
        self.last_checked_block = None

        if not self.w3.is_connected():
            raise Exception("Cannot connect to BSC network")

        logger.info(f"Connected to BSC - Block: {self.w3.eth.block_number}")

    def start_monitoring(self, deal_id, deal_info):
        self.monitored_deals[deal_id] = deal_info

        if self.last_checked_block is None:
            self.last_checked_block = self.w3.eth.block_number - 100

        logger.info(f"Started monitoring for deal {deal_id}")

    def stop_monitoring(self, deal_id):
        if deal_id in self.monitored_deals:
            del self.monitored_deals[deal_id]
            logger.info(f"Stopped monitoring for deal {deal_id}")

    async def check_transactions(self):
        if not self.monitored_deals:
            return []

        detected_payments = []
        current_block = self.w3.eth.block_number

        if self.last_checked_block is None:
            self.last_checked_block = current_block - 100

        from_block = self.last_checked_block + 1
        to_block = current_block

        if from_block > to_block:
            return []

        for deal_id, deal_info in list(self.monitored_deals.items()):
            try:
                token_address = TOKEN_CONTRACTS.get(deal_info['crypto'])
                if not token_address:
                    continue

                contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=TOKEN_ABI
                )

                transfer_filter = contract.events.Transfer.create_filter(
                    fromBlock=from_block,
                    toBlock=to_block,
                    argument_filters={
                        'to': Web3.to_checksum_address(ADMIN_WALLET_ADDRESS)
                    }
                )

                events = transfer_filter.get_all_entries()

                for event in events:
                    tx_hash = event['transactionHash'].hex()

                    if tx_hash in self.processed_txs:
                        continue

                    tx_receipt = self.w3.eth.get_transaction_receipt(tx_hash)

                    from_address = event['args']['from']
                    to_address = event['args']['to']
                    value = event['args']['value']

                    decimals = contract.functions.decimals().call()
                    amount = value / (10 ** decimals)
                    symbol = contract.functions.symbol().call()

                    if not self._verify_transaction_web3(
                        from_address, to_address, amount, symbol, deal_info, tx_receipt
                    ):
                        continue

                    confirmations = current_block - tx_receipt['blockNumber']

                    if confirmations >= CONFIRMATION_BLOCKS:
                        self.processed_txs.add(tx_hash)

                        payment_data = {
                            'deal_id': deal_id,
                            'tx_hash': tx_hash,
                            'from_address': from_address,
                            'amount': amount,
                            'token': symbol,
                            'confirmations': confirmations,
                            'timestamp': datetime.fromtimestamp(
                                self.w3.eth.get_block(tx_receipt['blockNumber'])['timestamp']
                            )
                        }

                        detected_payments.append(payment_data)

                        # 🔔 GROUP NOTIFICATION
                        tx_link = self.get_transaction_link(tx_hash)
                        message = f"""
💰 <b>New Deposit Received</b>

🆔 <b>Deal:</b> {deal_id}
🪙 <b>Token:</b> {symbol}
💵 <b>Amount:</b> {amount}
👤 <b>From:</b> <code>{from_address}</code>

🔗 <a href="{tx_link}">View on BscScan</a>
"""
                        await send_group_notification(message)

                        logger.info(f"Deposit detected & notified: {tx_hash}")

            except Exception as e:
                logger.error(f"Error checking deal {deal_id}: {e}")

        self.last_checked_block = to_block
        return detected_payments

    def _verify_transaction_web3(self, from_addr, to_addr, amount, symbol, deal_info, tx_receipt):
        try:
            if to_addr.lower() != ADMIN_WALLET_ADDRESS.lower():
                return False

            if from_addr.lower() != deal_info['seller_address'].lower():
                return False

            expected_amount = float(deal_info['amount'])

            if abs(amount - expected_amount) > (expected_amount * 0.001):
                return False

            if symbol.upper() != deal_info['crypto'].upper():
                return False

            if tx_receipt['status'] != 1:
                return False

            return True
        except Exception as e:
            logger.error(f"Verify error: {e}")
            return False

    def get_transaction_link(self, tx_hash):
        return f"https://bscscan.com/tx/{tx_hash}"

# Global instance
monitor = BlockchainMonitorWeb3()
