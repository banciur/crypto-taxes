# AI Developer Guideline – Target Architecture (Future Improvements)

This document describes the target, chain-agnostic, tax-accurate, auditable ledger and computation model. It is more comprehensive than the current minimal implementation and guides future work.

---

## 1. Purpose & Scope

Goal: implement a chain-agnostic, tax-accurate, auditable ledger for crypto assets and DeFi activity, optimized for the German 1-year rule.

The system should:
1. Ingest on-chain data, CEX exports, and protocol APIs.
2. Normalize them into a unified event ledger.
3. Track inventory lots, income, liabilities, and protocol positions.
4. Support complex DeFi constructs:
   - Multi-asset & multi-leg DEX trades
   - Cross-chain movements
   - Staking, restaking, and liquid staking derivatives
   - Lending/borrowing (Aave-style)
   - Uniswap v3 NFT liquidity
5. Produce derived views for holdings/valuations, taxable disposals, income, and reconciliation.

---

## 2. Design Principles

- Event-driven: every blockchain action → one `LedgerEvent` with ≥1 `LedgerLeg`s.
- Double-entry (derived view): sum of all legs per event (in EUR terms) ≈ 0 after fees.
- Append-only: never mutate events or lots; only add derived records.
- Deterministic: re-running ingestion/computation yields identical results.
- Chain-agnostic: works across Ethereum, L2s, Solana, etc.
- Policy-separated: data model is neutral; tax logic lives in `TaxPolicy`.
- Auditable: every derived value must reference raw event IDs and price sources.
- Configurable rules: one-year holding period, fee capitalization, LP treatment, etc.
 - Time handling: store all timestamps in UTC; convert to UTC at ingestion boundaries. Holding periods may be computed in a policy-specific timezone (e.g., Europe/Berlin).

---

## 3. Core Entities (Target Schema)

### 3.1 Identifiers
| Name | Example | Purpose |
|------|----------|---------|
| `ChainId` | `"eth-mainnet"` | chain scope |
| `AssetId` | `"eth:0xA0b86991..."` | canonical asset key |
| `WalletId` | `"hot_mm"` | user wallet |
| `ProtocolId` | `"uniswap_v3"` | protocol source |
| `PoolId` | `"uniswap_v3:ETH/USDC:3000"` | liquidity pool |
| `PositionId` | `"uv3:12345"` | unique protocol position |
| `LotId` | `"lot-abc123"` | inventory unit |
| `EventId` | `"evt-2025-001"` | ledger event |
| `TxHash` | blockchain tx reference |

### 3.2 Reference Tables
- `Asset`
- `Wallet`
- `PriceSnapshot`

### 3.3 Ledger Structures
```
LedgerEvent {
  id, tx_hash, chain_id, timestamp,
  event_type, protocol_id?, pool_id?, position_id?,
  legs: [LedgerLeg], metadata: Map
}

LedgerLeg {
  id, asset_id, quantity, wallet_id, counterparty?, fee_flag?, lot_link?
}
```

### 3.4 Inventory Lots
```
AcquisitionLot { id, acquired_event_id, acquired_leg_id,
  cost_eur_per_unit, acquired_timestamp }
Note: `asset_id` and `quantity_acquired` can be derived from the referenced `LedgerLeg`.
DisposalLink { id, disposal_leg_id, lot_id, quantity_used, proceeds_total_eur }
Note: `quantity_used` stores per-link allocation; if allocation becomes fractional, an allocation ratio can be added alongside quantity for precision.
```

### 3.5 Income & Liabilities
```
IncomeRecord { event_id, asset_id, quantity, fmv_eur, income_type }
DebtLot { lot_id, position_id, asset_id, principal_outstanding }
```

### 3.6 Protocol Positions
```
ProtocolPosition { position_id, protocol_id, wallet_id, position_type, attributes }
```

### 3.7 Policy & Derived Views
```
TaxPolicy {
  holding_period_days: 365,
  lot_selector: "FIFO" | "HIFO",
  treat_lp_mint_as_disposal: bool,
  treat_staking_rewards_as_income: bool,
  ...
}
```

---

## 4. Supported Event Types (Target)

| Category | Types |
|-----------|-------|
| Transfers | `TRANSFER`, `WRAP`, `UNWRAP`, `BRIDGE_IN`, `BRIDGE_OUT` |
| Trading | `BUY`, `SELL`, `SWAP` (multi-asset supported) |
| Liquidity | `LP_ADD`, `LP_REMOVE`, `LP_FEE_DISTRIBUTION` |
| Staking | `STAKE_START`, `STAKE_END`, `REWARD`, `INTEREST`, `RESTAKE` |
| Lending | `LOAN_PRINCIPAL_OUT`, `LOAN_PRINCIPAL_IN`, `INTEREST`, `LIQUIDATION` |
| Derivatives | `MINT_DERIV`, `REDEEM_DERIV` |
| Other | `AIRDROP`, `FORK`, `FEE`, `INTERNAL_MOVE`, `ADJUSTMENT` |

All events in the derived balanced view should have at least one negative and one positive leg (after including fees and counterparties) and approximately net to zero in EUR using snapshots.

Note on wallets: `wallet_id` lives on each `LedgerLeg` to enable single-event modeling of transfers and multi-wallet interactions.


---

## 7. Developer Rules (Target)

1. Never alter canonical event data after ingestion.
2. Generate migrations instead of destructive updates.
3. Always compute EUR values using nearest `PriceSnapshot` at event timestamp.
5. Preserve audit chain: any derived record must link to at least one `event_id`.
6. Support back-testing of `TaxPolicy` versions (frozen snapshot per report run).
7. Implement reconciliation checks between derived and on-chain balances.
8. Time handling: store UTC; compute holding periods in `Europe/Berlin`.
9. Precision: use `Decimal` with ≥18-digit precision; never floats.
10. Extensibility: new protocols should add event translators, not schema changes.

---

## 8. Output Artifacts (Target)

| Artifact | Purpose |
|-----------|----------|
| `TaxableDisposalView` | per-disposal gain/loss |
| `IncomeView` | taxable income |
| `BalanceSnapshot` | reconciliations |
| `TaxReportRun` + `TaxReportLine` | export to PDF/CSV |
| `AuditTrail` | JSON linking values to event hashes & price sources |

---

## 9. Quality & Testing (Target)

- Unit tests for each event type: verify correct lot creation/consumption.
- Golden-file tests for tax computations under multiple policies.
- Fuzz tests with randomized event streams to ensure determinism.
- Reconciliation tests: derived balances vs. chain indexer snapshots.

### Summary

This target architecture supports classic trades, multi-asset/cross-chain ops, lending/borrowing, liquid staking, and NFT-based LP positions while maintaining auditable lot tracking and the German 1-year exemption logic.
