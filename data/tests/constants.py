from accounts import account_chain_id_for
from domain.ledger import AssetId, EventLocation, WalletAddress

BTC = AssetId("BTC")
ETH = AssetId("ETH")
USDC = AssetId("USDC")
EUR = AssetId("EUR")
PLN = AssetId("PLN")
USD = AssetId("USD")

LOCATION = EventLocation.BASE
ETH_ADDRESS = WalletAddress("0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97")
ETH_TX_HASH = "0x32d8a1abfa7d9ded3ef0f5216ca241978c092e315566bbf4783210b73bc66e3e"

ALT_BASE_WALLET_ADDRESS = WalletAddress("0x1111111111111111111111111111111111111111")
LEDGER_WALLET_ADDRESS = WalletAddress("ledger")

ALT_BASE_WALLET = account_chain_id_for(location=LOCATION, address=ALT_BASE_WALLET_ADDRESS)
BASE_WALLET = account_chain_id_for(location=LOCATION, address=ETH_ADDRESS)
LEDGER_WALLET = account_chain_id_for(location=LOCATION, address=LEDGER_WALLET_ADDRESS)
