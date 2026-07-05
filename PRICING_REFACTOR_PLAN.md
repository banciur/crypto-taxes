# Pricing Service Refactor Plan

Branch: `refactor/pricing-service`

This is a living plan. Work proceeds **one step at a time**: implement a step, stop, let the
operator review and steer, then continue. Each step is a coherent, independently reviewable
commit. Completed work stays marked `[x]`; remaining work stays `[ ]`.

While executing, act as a senior developer: improve the quality of code you touch (naming,
duplication, simplification), but never silently — call out every such improvement when
reporting the step.

After any Python change, run `make code_fix` then `make test` from `data/`.

---

## Why

The pricing layer under `data/src/services/` is functional but muddled and has one dangerous
bug:

- HTTP clients, source adapters, the caching orchestrator, and the store all live together.
- The price-unavailability contract is **inverted**: a genuinely missing price hard-fails,
  while a transient network/5xx error is silently turned into a **fabricated EUR value** that
  flows into cost basis / proceeds (`valuation.py` `except Exception: return None`).
- The JSONL cache has a half-open/inclusive boundary off-by-one, no dedup, and no negative
  caching.
- Only `X → EUR` is ever resolved; there is no general cross-rate capability, no stable-token
  handling, and the base currency is hardcoded.

## Target design (decisions already made)

### Two-layer error model

**Layer 1 — price service (low-level).** Answers "can I produce a rate for `(base, quote, ts)`?"
with three outcomes:
1. a rate → return `Decimal`;
2. genuinely no price exists (backend answered, no data for this asset/pair/time) →
   return `None` (a first-class answer, **not** an exception);
3. operational failure (network down, 429/503 after retries exhausted, 500, bad JSON,
   timeout, bad API key) → raise `PriceClientError`. Never collapse this into `None`.

Layer-1 hierarchy (base in `src/clients/`):
```
PriceClientError(CryptoTaxesError)          # "a price backend failed operationally"
├── CoinDeskAPIError(PriceClientError)       # carries status_code, payload
└── OpenExchangeRatesAPIError(PriceClientError)
```
`PriceProvider.rate()` contract: returns `Decimal | None`, or raises `PriceClientError`.

**Layer 2 — acquisition/disposal valuation (high-level).** Consumes Layer 1. When automatic
resolution is impossible it raises `AcquisitionDisposalValuationError` (already carries
event/leg context): unpriceable valuation anchor, more than one unpriceable asset in an
event, one-sided event with nothing to solve against, fee-only unpriceable asset, negative
remainder, disagreeing anchored totals, non-positive balancing. Genuine `None` from Layer 1
feeds phase-2 remainder solving. A `PriceClientError` propagates untouched to `main.py`, which
records `FAILED` `SystemState`.

`RequiredPriceUnavailableError` and `RequiredValuationPriceUnavailableError` are **deleted**;
the anchor case raises `AcquisitionDisposalValuationError`.

### Storage: raw directional edges

Cache stores exactly what sources return — no numeraire normalization at write time.

| field | meaning |
|---|---|
| `base_id`, `quote_id` | ordered pair as fetched |
| `bucket_start`, `bucket_end` | half-open validity window `[start, end)` |
| `rate` | `Decimal`, **nullable** — `NULL` = negative cache ("asked, genuinely no price") |
| `source` | provenance |
| `fetched_at` | audit/debug |

- Unique key `(base_id, quote_id, bucket_start)` (dedup). Lookup:
  `base=? AND quote=? AND bucket_start <= ts < bucket_end`, newest `fetched_at` wins.
- Negative caching (`rate IS NULL`) is written **only** on the genuine-no-data path, **never**
  on a `PriceClientError` (otherwise a transient blip poisons the cache permanently).
- SQLite, following the `db/tx_cache_*` pattern, at `artifacts/price_cache.db`. No migration
  of the old JSONL cache.

### Resolution: single configurable pivot (numeraire)

`rate(base, quote, ts)`:
1. `base == quote` → `1`.
2. `base` is a configured stable pegged to the numeraire → its `→numeraire` edge is a
   synthetic `1` (never stored, never fetched).
3. a `base→quote` edge already in cache (incl. manual entries) → use it (cache-only, no
   network) — this is where "prefer direct" and manual overrides live.
4. otherwise pivot: resolve `base→numeraire` and `quote→numeraire` (each: cached edge →
   stable peg → fetch from the source that owns that asset), then divide. Cache the fetched
   **leg** edges only; never store the composed result.

Network fetches always target `asset→numeraire`, never `asset→base`. The composed result is
recomputed each query, so later manual edges are picked up with nothing stale to invalidate.

### Configuration

- Base accounting currency and pivot numeraire come from env; when unset default to
  **EUR base / USD numeraire**. `BASE_CURRENCY_ASSET_ID` stops being a hardcoded constant.
- Stable-asset set from config (env-overridable) with a small built-in default.

### Sources

- **Fiat → Open Exchange Rates** (unchanged, works).
- **Crypto → CoinMarketCap** (new). CoinDesk/CryptoCompare's free tier is retired: it caps at
  **100 API calls/month** (verified via a live 429 whose body read *"Rate limit exceeded.
  Please upgrade your account"* with `max_calls.month = 100`, `calls_made.month = 173`,
  monthly window resetting ~26 days out). That quota cannot price a real ledger, so CoinMarketCap
  replaces CoinDesk as the crypto source. The `src/clients/` boundary from Step 2 makes this a
  drop-in: a new client that implements `PriceSource`, selected by the resolver for crypto
  legs. The extracted CoinDesk client may be kept as a fallback or removed — decided in the step.

### Layering / placement

- `domain/pricing.py`: the pricing contract — `PriceProvider`, `PriceSource`, `PriceCache`,
  and `PriceRecord`. Innermost layer; depends on nothing below it.
- `src/clients/` (already holds `moralis.py`, `coinbase.py`): one module per provider
  (`coindesk.py`, `open_exchange_rates.py`, `coinmarketcap.py`). Each client talks HTTP AND
  implements `PriceSource.fetch_record(...) -> PriceRecord`, while keeping its
  raw API methods (`get_spot_historical_*`, `fetch_spot_candle`, `get_historical_rates`) for the
  scripts. `PriceClientError` lives in `src/clients/errors.py`. Clients may import `domain` but
  never `services`.
- `src/services/`: orchestration only — the resolver/`PriceService` and store wiring. No
  per-provider source adapters.
- `src/db/`: SQLite price cache.
- Dependency direction stays acyclic: `domain ← clients ← services`.

### Logging

`PriceService` logs only cache **misses** (i.e. when it hits the network). Cache hits are
not logged, to avoid flooding logs on every request.

### Deferred (out of scope, must remain unblocked)

- Multi-hop cross-rate resolution (arbitrary paths beyond a single numeraire pivot). The raw
  edge store does not block adding it later.

---

## Steps

- [x] **Step 0 — Branch and plan.** Create `refactor/pricing-service`; write this plan.

- [x] **Step 1 — Flip the price-unavailability contract + error taxonomy.**
  - `domain/pricing.py`: `PriceProvider.rate` → `Decimal | None`; delete
    `RequiredPriceUnavailableError`.
  - Sources return `None` on genuine no-data instead of raising (CoinDesk empty entries; OER
    missing currency). `fetch_record` → `PriceRecord` with nullable `rate`.
  - `PriceService.rate`: source `None` → return `None`; log only on cache miss / network
    fetch (not on cache hits).
  - `valuation._try_direct_rate`: `None` → return `None`; remove `except Exception: return
    None` so operational errors propagate.
  - Delete `RequiredValuationPriceUnavailableError`; anchor case keeps raising
    `AcquisitionDisposalValuationError`.
  - Fix JSONL read boundary to half-open (`valid_from <= ts < valid_to`).
  - Update tests: `valuation_test.py`, `projector_test.py`
    (`test_required_price_error` → assert `AcquisitionDisposalValuationError`; fakes return
    `None`), `price_service_test.py`, `coindesk_source_test.py`,
    `open_exchange_rates_source_test.py`.

- [x] **Step 2 — Extract low-level HTTP clients into the existing `src/clients/` package.**
  - Add `src/clients/errors.py` with `PriceClientError(CryptoTaxesError)`.
  - `src/clients/coindesk.py`: `CoinDeskClient` (was `_CoinDeskClient`),
    `SpotInstrumentOHLC`, `CoinDeskAPIError(PriceClientError)`, bucket helpers,
    `fetch_spot_history`, `fetch_spot_candle`.
  - `src/clients/open_exchange_rates.py`: `OpenExchangeRatesClient`, `HistoricalRates`,
    `OpenExchangeRatesAPIError(PriceClientError)`.
  - Reduce `coindesk_source.py` / `open_exchange_rates_source.py` to thin `PriceSource`
    adapters importing from `src/clients/`.
  - Update `scripts/coindesk/token_price.py` and test imports.

- [x] **Step 3 — SQLite edge store with negative caching.**
  - `db/price_cache.py`: SQLAlchemy model, base/init following `db/tx_cache_common.py`, and a
    repository implementing the `PriceCache` protocol; DB at `artifacts/price_cache.db`.
  - Half-open bucket lookup; unique-key dedup; nullable `rate` negative rows.
  - `PriceService`: on genuine `None` write a negative row; on quote write the edge; never
    negative-cache on `PriceClientError`. Log only on cache miss / network fetch, not on hits.
  - Rewire `build_price_service` and the CLI arg in `main.py`; retire `JsonlPriceStore`.
  - Migrate `price_store_test.py` / `price_service_test.py` to the SQLite store.
  - Consolidate price/store DTOs into one `PriceRecord` with nullable `rate` and provider-owned
    `fetched_at`; delete `PriceQuote`, `PriceCacheRecord`, and `PriceCacheEntry`.

- [x] **Step 4 — Consolidate the pricing contract into `domain`; clients implement `PriceSource`.**
  - Move `PriceRecord`, `PriceSource`, and `PriceCache` into `domain/pricing.py`, co-located
    with `PriceProvider`. Update all imports.
  - Make `CoinDeskClient` and `OpenExchangeRatesClient` implement
    `fetch_record(base, quote, ts) -> PriceRecord` — i.e. fold in the mapping that lives
    in the `*_source.py` adapters today (bucket → `PriceRecord`, cross-rate → `PriceRecord`,
    first-trade override, valid-window). Keep the raw client methods for the scripts.
  - Delete `services/coindesk_source.py` and `services/open_exchange_rates_source.py`; rewire
    `main.py` and the scripts/tests to use the clients directly.
  - Keep the graph acyclic: clients import `domain`, never `services`.
  - Delete `HybridPriceSource`; route fiat/crypto source selection through `PriceResolver`.
  - Tests: fold the source-mapping tests into the client tests (bucket→quote, cross-rate→quote,
    `None`-on-no-data, operational-error propagation).

- [ ] **Step 5 — Add CoinMarketCap crypto price source (replaces CoinDesk).**
  - `src/clients/coinmarketcap.py`: `CoinMarketCapClient` (auth via `X-CMC_PRO_API_KEY` header,
    base `https://pro-api.coinmarketcap.com`, retry/backoff), `CoinMarketCapAPIError(PriceClientError)`,
    raw historical-quote method(s), AND `fetch_record(base, quote, ts) -> PriceRecord`
    implementing `PriceSource` (per the Step 4 consolidation) — `rate=None` on genuine no-data,
    raise `CoinMarketCapAPIError` on operational failure; fetches `base → numeraire` (USD). No
    separate `services/` source file — the client is the source.
  - Config: add `coinmarketcap_api_key` (env, `data/.env` + `.env.example`).
  - Map CoinMarketCap's interval quote onto the edge store's half-open
    `[bucket_start, bucket_end)` window.
  - Optional: `scripts/coinmarketcap.py` helper mirroring the CoinDesk one for live spot checks.
  - Tests with a stubbed HTTP layer: quote mapping, `None`-on-no-data, operational-error propagation.
  - Live-verify a real crypto price returns.
  - Decide CoinDesk's fate: keep its client as a fallback source, or remove it.
  - Open questions to settle when starting the step:
    - **Plan/endpoint**: CoinMarketCap historical quotes (`/v2/cryptocurrency/quotes/historical`)
      require a paid tier; the free Basic plan is latest-only. Confirm the account grants
      historical access before building against it.
    - **Asset identity**: CoinMarketCap symbols collide across coins; prefer resolving via CMC
      numeric `id`, or accept symbol lookups initially and note the risk.

- [ ] **Step 6 — Single-pivot cross-rate resolver + configurable currencies + stable pegs.**
  - Config: base currency (env, default EUR), numeraire (env, default USD), stable-asset set
    (env + built-in default).
  - Implement the 4-step resolution rule (direct-cached preference, stable peg, pivot through
    numeraire, fetch legs from the owning source by asset class).
  - The resolver owns `base == quote → 1` (rule #1), short-circuiting before any store/source
    lookup so identity pairs never hit the network or build nonsense `X-X` instruments. This
    removes the "an asset priced in itself is 1" knowledge from the acquisition/disposal layer.
    Consequently `valuation._try_direct_rate` loses its only remaining logic (the
    `asset_id == BASE_CURRENCY_ASSET_ID` short-circuit) and becomes a redundant wrapper around
    `price_provider.rate(...)`: delete it and inline `price_provider.rate(group.asset_id,
    BASE_CURRENCY_ASSET_ID, timestamp)` at its two call sites (`_value_non_fee_groups`,
    `_value_fee_groups`), relying on the documented `None`-means-unpriceable contract.
  - Stable pegs synthesized (no store/network).
  - `BASE_CURRENCY_ASSET_ID` in `acquisition_disposal/constants.py` sourced from config.
  - Extend the existing `PriceResolver` from simple fiat/crypto routing to the full pivot
    algorithm; rewire `main.py` as needed.
  - Tests: pivot composition, stable resolution avoids network, direct-edge preference, a
    non-EUR base currency.

- [ ] **Step 7 — Cleanup, docs, TODO pruning.**
  - Simplify residual "vibed"/functional-experiment CoinDesk code surfaced in Steps 2–6.
  - Update `src/services/README.md`, add `src/clients/README.md`, update the price-services
    section of `data/README.md`, and update `doc/CURRENT.md` where documented
    pricing/valuation behavior changed (genuine-missing prices now remainder-solve; pricing is
    single-pivot cross-rate).
  - Remove the resolved price TODO lines from `doc/todo.txt`; record deferred multi-hop pivot
    as a TODO.
  - Delete this plan file (or archive it) once the work lands.
