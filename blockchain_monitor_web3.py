"""
Blockchain Monitor - Direct Web3 Reading (NO API NEEDED)
Reads directly from BSC blockchain for instant, unlimited transaction detection
"""
import asyncio
import logging
from datetime import datetime
from web3 import Web3
from web3.exceptions import BlockNotFound
from config import (
    ADMIN_WALLET_ADDRESS,
    BSC_RPC_URL,
    TOKEN_CONTRACTS,
    CONFIRMATION_BLOCKS,
    POLLING_INTERVAL
)

logger = logging.getLogger(__name__)

# USDT/USDC Token ABI (only Transfer event needed)
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
        self.monitored_deals = {}  # deal_id: deal_info
        self.processed_txs = set()  # Track processed transaction hashes
        self.last_checked_block = None
        
        # Verify connection
        if not self.w3.is_connected():
            raise Exception("Cannot connect to BSC network")
        
        logger.info(f"Connected to BSC - Block: {self.w3.eth.block_number}")
        
    def start_monitoring(self, deal_id, deal_info):
        """Start monitoring for a specific deal"""
        self.monitored_deals[deal_id] = deal_info
        
        # Set starting block if not set
        if self.last_checked_block is None:
            self.last_checked_block = self.w3.eth.block_number - 100  # Check last 100 blocks
        
        logger.info(f"Started monitoring for deal {deal_id}")
        
    def stop_monitoring(self, deal_id):
        """Stop monitoring a deal"""
        if deal_id in self.monitored_deals:
            del self.monitored_deals[deal_id]
            logger.info(f"Stopped monitoring for deal {deal_id}")
    
    async def check_transactions(self):
        """
        Check for new transactions by reading blockchain directly
        NO API NEEDED - reads Transfer events from blockchain
        """
        if not self.monitored_deals:
            logger.info("No deals being monitored")
            return []
        
        detected_payments = []
        current_block = self.w3.eth.block_number
        
        # If first run, start from recent blocks
        if self.last_checked_block is None:
            self.last_checked_block = current_block - 100
            logger.info(f"First run - starting from block {self.last_checked_block}")
        
        # Check new blocks since last check
        from_block = self.last_checked_block + 1
        to_block = current_block
        
        if from_block > to_block:
            logger.info("No new blocks to check")
            return []  # No new blocks
        
        logger.info(f"Checking blocks {from_block} to {to_block} for {len(self.monitored_deals)} deals")
        
        for deal_id, deal_info in list(self.monitored_deals.items()):
            try:
                # Get token contract
                token_address = TOKEN_CONTRACTS.get(deal_info['crypto'])
                if not token_address:
                    logger.warning(f"No token contract for {deal_info['crypto']}")
                    continue
                
                logger.info(f"Checking {deal_info['crypto']} transfers for deal {deal_id}")
                logger.info(f"  Token: {token_address}")
                logger.info(f"  Admin: {ADMIN_WALLET_ADDRESS}")
                logger.info(f"  Expected from: {deal_info['seller_address']}")
                logger.info(f"  Expected amount: {deal_info['amount']}")
                
                # Create contract instance
                contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=TOKEN_ABI
                )
                
                # Get Transfer events TO admin wallet
                try:
                    transfer_filter = contract.events.Transfer.create_filter(
                        fromBlock=from_block,
                        toBlock=to_block,
                        argument_filters={'to': Web3.to_checksum_address(ADMIN_WALLET_ADDRESS)}
                    )
                    
                    events = transfer_filter.get_all_entries()
                    logger.info(f"  Found {len(events)} Transfer events to admin wallet")
                    
                    for event in events:
                        tx_hash = event['transactionHash'].hex()
                        
                        # Skip if already processed
                        if tx_hash in self.processed_txs:
                            continue
                        
                        # Get transaction details
                        tx_receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                        tx = self.w3.eth.get_transaction(tx_hash)
                        
                        # Extract transfer details
                        from_address = event['args']['from']
                        to_address = event['args']['to']
                        value = event['args']['value']
                        
                        # Get token decimals
                        decimals = contract.functions.decimals().call()
                        amount = value / (10 ** decimals)
                        
                        # Get token symbol
                        symbol = contract.functions.symbol().call()
                        
                        # Verify transaction matches deal
                        if self._verify_transaction_web3(
                            from_address, to_address, amount, symbol, deal_info, tx_receipt
                        ):
                            # Check confirmations
                            confirmations = current_block - tx_receipt['blockNumber']
                            
                            if confirmations >= CONFIRMATION_BLOCKS:
                                # Mark as processed
                                self.processed_txs.add(tx_hash)
                                
                                # Add to detected payments
                                detected_payments.append({
                                    'deal_id': deal_id,
                                    'tx_hash': tx_hash,
                                    'from_address': from_address,
                                    'amount': amount,
                                    'token': symbol,
                                    'confirmations': confirmations,
                                    'timestamp': datetime.fromtimestamp(
                                        self.w3.eth.get_block(tx_receipt['blockNumber'])['timestamp']
                                    )
                                })
                                
                                logger.info(f"Payment detected for deal {deal_id}: {tx_hash}")
                
                except Exception as e:
                    logger.error(f"Error getting events: {e}")
                    # Continue with next deal
                    
            except Exception as e:
                logger.error(f"Error checking transactions for deal {deal_id}: {e}")
        
        # Update last checked block
        self.last_checked_block = to_block
        
        return detected_payments
    
    def _verify_transaction_web3(self, from_addr, to_addr, amount, symbol, deal_info, tx_receipt):
        """Verify if transaction matches deal requirements"""
        try:
            # Check if sent to admin wallet
            if to_addr.lower() != ADMIN_WALLET_ADDRESS.lower():
                return False
            
            # Check if from seller's address
            if from_addr.lower() != deal_info['seller_address'].lower():
                return False
            
            # Check amount (with small tolerance for rounding)
            expected_amount = float(deal_info['amount'])
            
            # Allow 0.1% tolerance
            if abs(amount - expected_amount) > (expected_amount * 0.001):
                return False
            
            # Check token symbol
            if symbol.upper() != deal_info['crypto'].upper():
                return False
            
            # Check transaction was successful
            if tx_receipt['status'] != 1:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying transaction: {e}")
            return False
    
    def get_transaction_link(self, tx_hash):
        """Generate BscScan transaction link"""
        return f"https://bscscan.com/tx/{tx_hash}"


# Global monitor instance
monitor = BlockchainMonitorWeb3()
