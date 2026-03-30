# Coinbase Scripts

Purpose of scripts in this folder:

- `account_history.py`: calls Coinbase Track API via `CoinbaseClient` and prints raw account-history transactions as JSON.
- `cache_lookup.py`: inspects the local Coinbase cache by Coinbase event external id and prints matching cached transactions plus related account payloads.
