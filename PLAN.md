# Corrections / Transformations Layer — Plan

This document summarizes the current discussion (Dec 2025) and records the decisions we made about introducing “corrections” to the crypto-taxes pipeline. It is intended to be a living development plan for the next iteration of the system.

Canonical domain reference remains `doc/CURRENT.md`.

---

## Problem Statement

The current pipeline ingests data sources (Kraken CSV, Moralis on-chain ERC20) into `LedgerEvent`s and then runs:

- inventory/lot creation + FIFO matching (`InventoryEngine`)
- tax event generation (`generate_tax_events`) based on disposals and `EventType.REWARD`

In practice, raw ingest streams contain many cases that need manual or automatic correction:

- Missing history: untracked acquisitions/holdings needed so transfers don’t push wallet balances negative.
- Non-taxable income at receipt: e.g. employer bonus where income tax was already paid.
- Spam/scam on public chains: worthless token/NFT transfers that should be ignored.
- Multi-step operations: bridges, CEX↔chain moves, and other sequences that, if interpreted naively, produce incorrect tax outcomes (e.g., “send looks like disposal”, “receive looks like reward”, which resets holding period and creates false income).

We want a clean “correction layer” between ingestion and downstream processing that:

- produces a **corrected (effective) ledger event stream** for inventory/taxes/wealth
- keeps **raw data intact and auditable**
- supports **manual-first** workflows, with optional heuristics later

---

## Current System (Snapshot)

From `doc/CURRENT.md`:

- A `LedgerEvent` has `timestamp`, `origin` (location + external id), `ingestion`, `event_type`, and `legs`.
- A `LedgerLeg` has `asset_id`, signed `quantity`, `wallet_id`, and `is_fee`.
- Inventory:
  - uses FIFO lots per **asset** (not per wallet)
  - tracks **per-wallet balances** for non-EUR legs; negative balances raise an error
  - currently skips lot creation/matching for `EventType.TRANSFER` (transfer updates balances only); planned change: still skip non-fee transfer legs for lot logic but process `is_fee=True` legs as disposals
- Taxes:
  - disposals within 1-year window are taxable gain
  - `EventType.REWARD` is taxed as income at receipt (lot proceeds valued at cost basis)

Existing “corrections” are currently scattered:

- Seed lots via `artifacts/seed_lots.csv` (loaded as `SeedEvent`s and persisted to the DB) to fix missing history.
- Kraken importer does source-specific ignores and cleanup.
- On-chain importer currently maps:
  - `wallet_id` = address (not chain-scoped yet)
  - `asset_id` = contract address (not canonicalized yet)

---

## Decisions We Made (Explicit)

### 1) Layering: Raw → Corrections → Effective

We will divide the pipeline into:

1. **Raw ingestion**: importers produce normalized but source-faithful `LedgerEvent`s.
2. **Corrections/transformations layer**: consumes raw events and produces an **effective event stream** used for inventory/taxes/wealth.
3. **Downstream processing**: inventory, tax, wealth, UI read from the effective stream.

Corrections must be:

- deterministic (effective stream is reproducible from raw + corrections)
- auditable (show which raw events were changed/ignored/linked)
- keyed by stable identifiers (not random UUIDs)

### 2) Identity: Canonical Assets, Chain-Scoped Wallets

- **Assets (`asset_id`) are canonical and chain-unrelated**.
  - Example: “USDC” is one canonical asset.
  - But ingestion must map on-chain `(chain, contract_address)` → canonical `asset_id`.
- **Wallets (`wallet_id`) are chain-scoped**.
  - Same address on different chains is tracked separately.
  - Proposed formatting: `"<chain>:<address>"` (e.g., `base:0x333...`, `eth:0x333...`).

Rationale:

- Canonical assets ensure bridges don’t reset lot holding period as long as they are treated as transfers.
- Chain-scoped wallets keep balances accurate and avoid cross-chain mixing.

### 3) Default Tax Classification for On-Chain Movements

- **Incoming transfers** (not-ours → ours) default to **taxable `REWARD`**.
- **Outgoing transfers** (ours → not-ours) can represent spending; do **not** block pipeline due to lack of a matching receive. Treat as disposal by default.

However:

- The corrections layer must be able to reclassify specific cases (e.g., bridges, CEX↔chain deposits) so we don’t create false taxable `REWARD`s.

### 4) Missing History / Seeding

- When inventory processing encounters an **insufficient wallet balance** (negative), the pipeline should **stop** and force fixing.
- Fixing is manual initially (like today) but may become partially automatic:
  - **Automatic seed mode**: assume almost-zero starting worth and “tax-free” (distant/unknown acquisition).
  - **Manual seed mode**: user provides acquisition date and EUR worth/cost.

### 5) “Already Taxed” Income

- Some acquisition events that look like `REWARD` should be **excluded from tax due** (no income tax at receipt), but must still:
  - update balances/wealth
  - create lots / cost basis for later disposals

This implies a **tax override** mechanism that suppresses generating the `TaxEventKind.REWARD` for selected events/legs.

### 6) Spam / Scam Transfers

- Ingest everything first; add manual/automatic classification later.
- Corrections must support **ignoring** spam/scam tokens/NFTs, ideally by:
  - `(chain, contract_address)` mapping to a “spam/ignore” classification
  - or by explicit event selectors (tx hash)

### 7) Bridging and Multi-Step Operations

Goal: prevent false disposals / false rewards and preserve holding period.

- Bridging is **non-taxable by default** when it represents transfer between your own wallets.
- Bridging should not require introducing a special `EventType`. It should become a transfer between your wallets in the effective ledger.
- A bridge can have two kinds of fees:
  - native network fee (e.g., ETH gas)
  - bridge fee in the bridged asset (e.g., 100 USDC sent, 99.8 USDC received)

### 8) Linking and Collapsing (Manual “Combining”)

We will support manual linking of raw events into one effective event.

- For CEX↔chain and bridges, the effective ledger should **collapse to one `TRANSFER` event**.
- We accept **timing loss** (a single timestamp cannot represent both “sent” and “received”).

### 9) `outside` Wallet Semantics

- `outside` is a boundary wallet representing “unknown/untracked external world”.
- It can represent:
  - your untracked wallets
  - real counterparties (goods/services/people)
- It is valid for outgoing transfers to `outside` to be real disposals (spending).

For CEX limitations (e.g., not knowing withdrawal destination), `outside` remains the default counterparty unless a manual link provides more structure.

### 10) `TRANSFER` Semantics: Fee Legs Are Tax-Visible

We will adjust inventory processing so `EventType.TRANSFER` continues to represent non-taxable wallet-to-wallet movements **without affecting lot holding periods**, while still accounting for fees:

- Non-fee legs in a `TRANSFER` do not create lots and do not consume lots (holding period continuity is preserved).
- Legs with `is_fee=True` **do** consume lots and generate disposal links (so fees are valued and can affect 1-year taxability).

Practical modeling rule:

- If a transfer has an in-asset fee (e.g., bridge sends 100 USDC and receives 99.8 USDC), represent the *moved amount* as `99.8` in the non-fee transfer legs, and represent the `0.2` delta as a separate `is_fee=True` leg. Do not embed the delta by making the outbound leg larger than the inbound leg (it would become invisible or double-counted depending on semantics).

### 11) Deferred: Exchange Fee Normalization

We explicitly decided to leave “how to normalize CEX fees” for a future iteration.

---

## Proposed Correction Layer: Conceptual Model

### Inputs / Outputs

- Input: `raw_events: list[LedgerEvent]` (from all importers, sorted by timestamp).
- Output: `effective_events: list[LedgerEvent]` used for inventory + taxes + wealth.

### Stable Selectors

Corrections must reference events by stable keys, not generated UUIDs.

Primary selector:

- `origin.location + origin.external_id`

Optionally include `ingestion` if needed to disambiguate:

- `(ingestion, origin.location, origin.external_id)`

Examples:

- Kraken: `(KRAKEN, refid)`
- On-chain: `(ETHEREUM/BASE/..., tx_hash)`

### Correction Primitives (Minimum Set, v0)

The initial set should match `data/src/domain/correction.py` (kept intentionally small for v0):

1. **Spam marker**
   - event-level ignore keyed by `event_origin`.
   - v0 scope: ignore whole events; leg-level ignore is a later extension.

2. **Already-taxed marker**
   - suppress reward income taxation keyed by `event_origin`, while keeping balances/lots intact.

3. **Seed event (synthetic event)**
   - a minimal “insert event” shape (`timestamp` + `legs`) to fix missing history and allow processing to continue.

4. **Link marker (derived effective event)**
   - a derived event (`timestamp` + `legs`) that also records `event_origins: list[EventOrigin]` consumed by the link.
   - intended uses: bridge, CEX↔chain transfer, manual “this was self-transfer not income”.

5. **Identity mapping (separate but required)**
   - wallet mapping: chain-scoped wallet ids
   - asset registry mapping: `(chain, contract_address)` → canonical asset id
   - spam classification: mark asset contracts as ignored/spam

6. **Grouping/linking for UI (optional, later)**
   - attach `operation_id` to related raw/effective events for presentation without changing accounting.
   - Not required for correctness but makes review easier.

---

## How We Will Model the Tricky Cases

### A) Bridging (manual linking)

**Raw (naive) interpretation**:

- Chain A outgoing: looks like disposal (could trigger taxable event, changes “tax-free pool”)
- Chain B incoming: looks like taxable `REWARD` (creates a new lot at receipt, resets holding period)

**Correct interpretation**:

- It’s a transfer between owned wallets (non-taxable; lot continuity preserved).

**Effective ledger (collapsed)**:

- Emit one `TRANSFER` event:
  - `-net_amount` from `from_wallet` (chain A wallet)
  - `+net_amount` to `to_wallet` (chain B wallet)
  - `timestamp`: use the outgoing timestamp (chosen by user/operation)

**Fees**:

With the planned `TRANSFER` semantics change (fee legs are tax-visible), fees can be represented either:

- as `is_fee=True` legs on the same effective `TRANSFER` event (preferred), or
- as separate `OPERATION` events (still valid, but not required for correctness).

For bridges specifically:

- Gas/native fee: `is_fee=True` leg in the native asset (requires native token ingestion first).
- Bridge fee in bridged asset (sent - received): `is_fee=True` leg in the bridged asset.

This ensures bridge fees are valued and taxed correctly (e.g., within 1-year window) without resetting holding periods for the transferred amount.

### B) CEX ↔ Chain transfers (manual linking, heuristics later)

Goal: avoid double counting and false income when funds move between Kraken and an on-chain wallet.

**Approach**:

- Create a `LinkMarker` that consumes the Kraken withdrawal refid origin and the on-chain incoming tx hash origin.
- The effective ledger emits one collapsed `TRANSFER`:
  - `-amount` from `wallet_id="kraken"`
  - `+amount` to `wallet_id="<chain>:<address>"`
- Consume/omit the linked raw events from the effective stream (but keep them stored for audit/UI).

Later we may add “suggested matches” heuristics (amount + time window + asset) but keep user confirmation.

### C) Already-taxed rewards (manual override)

**Default**:

- Incoming transfer → `REWARD` → taxed at receipt.

**Override**:

- Keep the acquisition (balance + lot + cost basis).
- Suppress generating the income tax event for that reward acquisition by attaching an `AlreadyTaxed` marker to its `event_origin`.

### D) Spam/scam tokens/NFTs

**Default**:

- ingest everything.

**Correction**:

- ignore by asset contract + chain (preferred) or by explicit event.
- For ERC20 spam (v0): ignore events so they don’t affect balances, inventory, or taxes.

---

## Implementation Notes (Constraints from Current Domain)

These constraints shape how corrections must be represented to remain tax-correct:

- Planned change: `TRANSFER` events should process **fee legs only**.
  - Non-fee transfer legs: update wallet balances only; do not create or consume lots (holding period continuity).
  - Fee legs (`is_fee=True`): treated as disposals (consume lots, valued via EUR legs or price provider), so fees remain tax-visible.

- Lots are tracked by asset, not wallet.
  - Works well with canonical assets for bridges.
  - Requires careful asset registry mapping on-chain.

- Wallet balances enforce non-negative per wallet per asset.
  - Negative should remain a hard error (forces seeding/corrections).

---

## UI ↔ Data Two-way Communication (Local-First)

We will keep the SQLite database `crypto_taxes.db` as the shared contract between `data/` and `ui/`, but enable two-way workflows by having the UI trigger Python actions.

Chosen approach:

- UI reads ledger/inventory/tax views from `crypto_taxes.db`.
- When the user creates/edits corrections in the UI, the **React server-side** (Next.js) performs **system calls** to run Python (e.g., via `uv run ...`) to:
  - persist corrections to the database, and
  - rebuild derived tables (effective ledger, lots, disposals, tax events).
- UI refreshes by re-reading from the same database.

This keeps domain logic in Python (minimal duplication in TypeScript) and avoids treating the UI as the source of truth for tax semantics.

## Data Storage Options (Plan)

We have two viable approaches for storing corrections; start with DB-backed storage to support UI editing, and keep file-backed as an optional bootstrapping path.

### Option 1 (Start): Persist corrections + operations in DB

- Add tables for correction primitives that map closely to `data/src/domain/correction.py`:
  - spam markers (`Spam`)
  - already-taxed markers (`AlreadyTaxed`)
  - seed events (`SeedEvent` events)
  - link markers (`LinkMarker` events + their consumed `event_origins`)
  - asset registry / mappings (canonical asset ids; spam classification)
- Derived tables remain rebuildable (effective events, lots, disposals, tax events).

### Option 2 (Optional): File-backed corrections (local)

- Store corrections in `artifacts/` (local, not committed) as JSON/YAML/CSV.
- Useful for early bootstrapping or emergency edits, but less queryable than DB tables.

---

## Development Plan (Milestones)

### Milestone 0 — Conventions / Identity (required for everything)

- Define canonical formats:
  - chain-scoped `wallet_id`
  - asset registry mapping `(chain, contract_address)` → canonical `asset_id`
  - spam classification storage (initially manual)

Acceptance:

- same address on different chains becomes distinct wallets
- same canonical asset can be held across wallets/chains

### Milestone 1 — Correction Data Model + Engine (minimal primitives)

- Define correction primitives:
  - `Spam` (ignore event)
  - `AlreadyTaxed` (reward tax override)
  - `SeedEvent` (insert synthetic event)
  - `LinkMarker` (insert derived effective event and record consumed origins)
- Implement deterministic transformation pipeline:
  - input raw events
  - apply mappings/ignores/links
  - output effective events
  - preserve an audit log: which raw events were consumed/rewritten

Acceptance:

- effective stream is reproducible from raw + corrections
- UI/CLI can print “why” an event was ignored/linked

### Milestone 2 — Fees via `is_fee` Legs (including in `TRANSFER`)

- Change inventory processing so `TRANSFER` events continue to preserve holding period, but still produce disposal links for fee legs:
  - treat `is_fee=True` legs in `TRANSFER` as disposals
  - ignore non-fee transfer legs for lot creation/consumption
- Use this modeling for bridge fees and on-chain gas fees (once native tokens are ingested).

Acceptance:

- bridge fee impacts inventory/taxes as disposal of the bridged asset (without resetting holding period for the bridged transfer)
- fees remain visible but not counted as income

### Milestone 3 — Manual workflow ergonomics

- CLI/UI operations:
  - list raw candidate events
  - create a link operation (bridge / CEX transfer)
  - mark spam assets / ignore events
  - mark reward as already taxed
  - manage seeds when negative balance occurs

Acceptance:

- user can resolve real-world mismatches without editing importer code

### Milestone 4 — Heuristics as “suggestions” (optional, later)

- Propose link candidates (do not auto-apply):
  - amount + time window + asset match
  - allowlist bridge routers/contracts
  - optional chain-to-chain bridging patterns

Acceptance:

- suggestions reduce manual work without silently changing taxes

---

## Open Questions (Remaining)

These are intentionally unresolved or depend on future work:

- Exchange fee normalization (explicit vs implicit modeling): deferred.
- Native token ingestion for gas fee modeling: Moralis importer currently ignores native transfers.
- Handling ambiguous “incoming reward vs deposit from self”:
  - We decided default is taxable `REWARD`.
  - Corrections must be strong enough to reclassify self-transfer/CEX deposits to avoid over-taxing.

---

## Worked Examples (Conceptual)

### Example 1: Bridge USDC (with bridge fee)

Raw:

- ETH tx: outflow 100 USDC from `eth:0x333` to bridge contract
- BASE tx: inflow 99.8 USDC to `base:0x333`

Corrections:

- create a `LinkMarker` that consumes both raw tx origins and emits an effective `TRANSFER` event moving `99.8` USDC:
  - non-fee legs: `-99.8 USDC` from `eth:0x333`, `+99.8 USDC` to `base:0x333`
  - fee leg: `-0.2 USDC` from `eth:0x333`, `is_fee=True`
- (later) include gas fee as a fee leg once native fee ingest exists (e.g., `-0.005 ETH`, `is_fee=True`)

Effective:

- one `TRANSFER` moving 99.8 USDC from ETH wallet to BASE wallet, with an additional `is_fee=True` leg disposing 0.2 USDC

### Example 2: Employer bonus already taxed

Raw:

- incoming ETH/USDC/etc recognized as `REWARD`

Correction:

- add an `AlreadyTaxed` marker for the reward’s `event_origin`

Effective:

- balances/lots exist
- income tax at receipt suppressed

### Example 3: Spam token transfer

Raw:

- incoming ERC20 transfer for spam token contract

Correction:

- ignore by `(chain, contract_address)` → spam

Effective:

- spam legs/events removed from ledger/inventory/tax
