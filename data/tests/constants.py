from domain.ledger import AccountChainId, AssetId, ChainId, WalletAddress

BTC = AssetId("BTC")
ETH = AssetId("ETH")
EUR = AssetId("EUR")

KRAKEN_WALLET = AccountChainId("kraken")
OUTSIDE_WALLET = AccountChainId("outside")
SPOT_WALLET = AccountChainId("spot")
LEDGER_WALLET = AccountChainId("ledger")

CHAIN = ChainId("base")
ETH_ADDRESS = WalletAddress("0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97")
