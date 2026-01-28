"""
Transaction Handler - Send USDT/USDC transactions (release/refund)
"""
import logging
from web3 import Web3
from eth_account import Account
from config import (
    ADMIN_WALLET_ADDRESS,
    ADMIN_WALLET_PRIVATE_KEY,
    BSC_RPC_URL,
    TOKEN_CONTRACTS,
    MAX_GAS_PRICE
)

logger = logging.getLogger(__name__)

# ERC20 ABI for transfer function
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]


class TransactionHandler:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
        self.account = Account.from_key(ADMIN_WALLET_PRIVATE_KEY)
        
        # Verify connection
        if not self.w3.is_connected():
            raise Exception("Failed to connect to BSC network")
        
        logger.info(f"Transaction handler initialized. Admin wallet: {ADMIN_WALLET_ADDRESS}")
    
    async def send_token(self, to_address, amount, token_symbol):
        """
        Send USDT/USDC to specified address
        
        Args:
            to_address: Recipient address
            amount: Amount to send (in token units, e.g., 100 USDT)
            token_symbol: 'USDT' or 'USDC'
        
        Returns:
            dict: Transaction result with tx_hash and status
        """
        try:
            # Get token contract address
            token_address = TOKEN_CONTRACTS.get(token_symbol)
            if not token_address:
                raise ValueError(f"Unsupported token: {token_symbol}")
            
            # Create contract instance
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ERC20_ABI
            )
            
            # Get token decimals
            decimals = contract.functions.decimals().call()
            
            # Convert amount to token units
            amount_in_units = int(float(amount) * (10 ** decimals))
            
            # Check balance
            balance = contract.functions.balanceOf(
                Web3.to_checksum_address(ADMIN_WALLET_ADDRESS)
            ).call()
            
            if balance < amount_in_units:
                raise ValueError(
                    f"Insufficient balance. Required: {amount} {token_symbol}, "
                    f"Available: {balance / (10 ** decimals)} {token_symbol}"
                )
            
            # Check BNB balance for gas
            bnb_balance = self.w3.eth.get_balance(ADMIN_WALLET_ADDRESS)
            if bnb_balance < self.w3.to_wei(0.001, 'ether'):
                raise ValueError(
                    f"Insufficient BNB for gas. Balance: {self.w3.from_wei(bnb_balance, 'ether')} BNB"
                )
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(ADMIN_WALLET_ADDRESS)
            
            # Get current gas price
            gas_price = self.w3.eth.gas_price
            max_gas_price_wei = self.w3.to_wei(MAX_GAS_PRICE, 'gwei')
            
            if gas_price > max_gas_price_wei:
                logger.warning(f"Gas price too high: {self.w3.from_wei(gas_price, 'gwei')} gwei")
                gas_price = max_gas_price_wei
            
            # Build transfer transaction
            transaction = contract.functions.transfer(
                Web3.to_checksum_address(to_address),
                amount_in_units
            ).build_transaction({
                'from': ADMIN_WALLET_ADDRESS,
                'nonce': nonce,
                'gas': 100000,  # Standard gas limit for token transfer
                'gasPrice': gas_price
            })
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(
                transaction,
                private_key=ADMIN_WALLET_PRIVATE_KEY
            )
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = self.w3.to_hex(tx_hash)
            
            logger.info(f"Transaction sent: {tx_hash_hex}")
            
            # Wait for transaction receipt (with timeout)
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                
                if receipt['status'] == 1:
                    logger.info(f"Transaction successful: {tx_hash_hex}")
                    return {
                        'success': True,
                        'tx_hash': tx_hash_hex,
                        'amount': amount,
                        'token': token_symbol,
                        'to': to_address,
                        'gas_used': receipt['gasUsed'],
                        'bscscan_link': f"https://bscscan.com/tx/{tx_hash_hex}"
                    }
                else:
                    logger.error(f"Transaction failed: {tx_hash_hex}")
                    return {
                        'success': False,
                        'error': 'Transaction reverted',
                        'tx_hash': tx_hash_hex
                    }
                    
            except Exception as e:
                logger.error(f"Error waiting for receipt: {e}")
                return {
                    'success': False,
                    'error': f'Transaction sent but receipt timeout: {str(e)}',
                    'tx_hash': tx_hash_hex,
                    'bscscan_link': f"https://bscscan.com/tx/{tx_hash_hex}"
                }
        
        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_token_balance(self, token_symbol):
        """Get token balance of admin wallet"""
        try:
            token_address = TOKEN_CONTRACTS.get(token_symbol)
            if not token_address:
                return 0
            
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ERC20_ABI
            )
            
            balance = contract.functions.balanceOf(
                Web3.to_checksum_address(ADMIN_WALLET_ADDRESS)
            ).call()
            
            decimals = contract.functions.decimals().call()
            
            return balance / (10 ** decimals)
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0
    
    def get_bnb_balance(self):
        """Get BNB balance of admin wallet"""
        try:
            balance = self.w3.eth.get_balance(ADMIN_WALLET_ADDRESS)
            return self.w3.from_wei(balance, 'ether')
        except Exception as e:
            logger.error(f"Error getting BNB balance: {e}")
            return 0


# Global transaction handler instance
tx_handler = TransactionHandler()
