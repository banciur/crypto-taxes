# Moralis Scripts

Purpose of scripts in this folder:

- `client_fetch.py`: calls Moralis directly via `MoralisClient`, prints raw API transactions as JSON (`--print-count` defaults to `3`, use `all` to print everything), then prints `printed/returned` counts.
- `fetch_wallet_history.py`: runs the Moralis sync/import flow (through `MoralisService` + importer) and writes normalized events to a JSON file.
- `cache_lookup.py`: inspects the local Moralis cache DB by record id or transaction hash.
