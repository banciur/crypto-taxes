from domain.ledger import AccountChainId, AssetId, EventLocation, WalletAddress

BTC = AssetId("BTC")
ETH = AssetId("ETH")
EUR = AssetId("EUR")

OUTSIDE_WALLET = AccountChainId("outside")
SPOT_WALLET = AccountChainId("spot")
LEDGER_WALLET = AccountChainId("ledger")

LOCATION = EventLocation.BASE
ETH_ADDRESS = WalletAddress("0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97")
ETH_TX_HASH = "0x32d8a1abfa7d9ded3ef0f5216ca241978c092e315566bbf4783210b73bc66e3e"
