# Moralis Scripts

Purpose of scripts in this folder:

- `client_fetch.py`: calls Moralis directly via `MoralisClient`, prints raw API transactions as JSON.
- `fetch_wallet_history.py`: runs the Moralis sync/cache/process flow (through `MoralisService` / `MoralisImporter` / `MoralisClient`) and dumps events to a JSON file.
- `cache_lookup.py`: inspects the local Moralis cache DB by record id or transaction hash.
