"""
Check specific transaction to debug why it's not detected
"""
from web3 import Web3
from config import ADMIN_WALLET_ADDRESS, TOKEN_CONTRACTS

# Your transaction from screenshot
TX_HASH = "0xb921e63ea17c434546...e8ee00e6dfc78d573a29"  # Replace with full hash
SELLER_ADDRESS = "0x4A23565310e6b3D9d1ce0F2Dcf142d3a8757eb67"  # From screenshot
BUYER_ADDRESS = "0x5c2f43F8f87dDE5e72C2309a3F044dcf53B2866F6"  # From screenshot
ADMIN_WALLET = "0x1B87349DD046F7A6c9c63FBbA58108943a942092"  # From screenshot

print("=" * 70)
print("TRANSACTION DEBUG")
print("=" * 70)

# Connect to BSC
w3 = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org/"))
print(f"Connected to BSC: {w3.is_connected()}")
print(f"Current block: {w3.eth.block_number}")
print()

# Check if transaction exists
print("Checking transaction...")
print(f"TX Hash: {TX_HASH}")
print()

try:
    # Get transaction receipt
    tx_receipt = w3.eth.get_transaction_receipt(TX_HASH)
    print(f"✅ Transaction found!")
    print(f"   Status: {'Success' if tx_receipt['status'] == 1 else 'Failed'}")
    print(f"   Block: {tx_receipt['blockNumber']}")
    print(f"   From: {tx_receipt['from']}")
    print(f"   To: {tx_receipt['to']}")
    print()
    
    # Check logs for Transfer event
    print("Checking Transfer events...")
    for log in tx_receipt['logs']:
        # Transfer event signature
        transfer_topic = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
        if log['topics'][0].hex() == transfer_topic:
            from_addr = '0x' + log['topics'][1].hex()[-40:]
            to_addr = '0x' + log['topics'][2].hex()[-40:]
            print(f"   Transfer event found:")
            print(f"   From: {from_addr}")
            print(f"   To: {to_addr}")
            print(f"   Token: {log['address']}")
            
            if to_addr.lower() == ADMIN_WALLET.lower():
                print(f"\n   ✅ This IS a transfer TO admin wallet!")
            else:
                print(f"\n   ❌ This is NOT to admin wallet")
                print(f"   Expected: {ADMIN_WALLET}")
                print(f"   Got: {to_addr}")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 70)
print("CHECKING ADMIN WALLET BALANCE")
print("=" * 70)

# Check USDT balance
usdt_contract = w3.eth.contract(
    address=Web3.to_checksum_address(TOKEN_CONTRACTS['USDT']),
    abi=[{
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }]
)

balance = usdt_contract.functions.balanceOf(ADMIN_WALLET).call()
print(f"Admin wallet USDT balance: {balance / 1e18} USDT")

if balance > 0:
    print("✅ Admin wallet HAS USDT!")
else:
    print("❌ Admin wallet has NO USDT")

print("=" * 70)
