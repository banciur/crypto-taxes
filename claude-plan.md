# Plan: valuing events whose assets have no market price

Working document for an in-progress task. Written 2026-07-14 at the end of an
investigation session so work can resume from a cold start.

## How to resume

Read this file, then `doc/CURRENT.md` and `doc/LOT_MATCHING.md`, then the code and
data listed under "Where things live". The investigation below is already verified
against local data — trust it, but re-verify anything you intend to change.

Nothing has been implemented yet. No code was changed during the investigation.

## Where things live

Code:

- Valuation: `data/src/domain/acquisition_disposal/valuation.py`
  - `_solve_unknown_rate` — remainder-solves a single unpriceable asset
  - `_rebalance_known_rates` — mid-points the weakest valuation tier so the event balances
  - `_rate_in_base_currency` — checks the override map **before** the price provider
- Projector loop: `data/src/domain/acquisition_disposal/projector.py`
- Quantity projection (phase 1): `data/src/domain/acquisition_disposal/quantities.py`
- Valuation tiers: `data/src/domain/acquisition_disposal/constants.py`
- Price overrides: `data/src/domain/price_override.py`, `data/src/db/price_overrides.py`
- Price service / asset map: `data/src/services/price_service.py`, `artifacts/cmc_asset_map.json`
- Moralis asset id derivation: `data/src/importers/moralis/moralis_importer.py:129` (`erc20_asset_id`)

Local data (SQLite, all under `artifacts/`):

- `crypto_taxes.db` — `corrected_ledger_events` / `corrected_ledger_legs`, `acquisition_lots`,
  `disposal_links`, `system_state`
- `corrections.db` — `ledger_corrections`, `ledger_correction_legs`, `ledger_correction_sources`
- `price_overrides.db` — `price_overrides`
- `price_cache.db` — `price_edges` (`rate IS NULL` marks a negative-cached, genuinely missing price)
- `transactions_cache.db` — `moralis_transactions` (raw payloads: token symbol, **contract address**,
  decimals, direction). This is the ground truth for asset identity.

## Current state

The pipeline is **FAILED**:

```
status = FAILED
stage  = ACQUISITION_DISPOSAL
error  = More than one distinct non-fee asset is unpriceable in the same event:
         assets=fcbBTC,pfcbBTC.
         event_origin=BASE/0x7a3914031616e4002dc8f620f4fadeb1fa59f5b03a59b17196d2e8db83c7e256
         @2024-10-20T14:25:47+00:00
```

Note this is the fcbBTC **exit**, not the stake. The stake was fixed with a manual override,
the run advanced one event and died on the next. That rerun-whack-a-mole is itself part of
the problem.

## The problem

Events are valued independently. The system asks the price service for EUR rates, applies
event-specific `PriceOverride`s, and can solve **exactly one** missing non-fee asset as the
remainder implied by the priced opposite side of the same event.

It fails when:

- more than one distinct non-fee asset in an event is unpriceable, or
- the event is **one-sided** (all non-fee legs the same sign) and has no direct price —
  remainder solving needs opposing value and there is none.

This bites farm, LP, staking and reward tokens: CoinMarketCap does not price them, and the
event being valued often has no directly priceable leg. Today the only escape is a hand-authored
`PriceOverride` per (event, asset), which is laborious, undocumented, and inconsistent.

### The three cases driving this

**fcbBTC / pfcbBTC on Base** — lending-pool entry, then stake, then exit.
- Entry `0x797daf8f…` (2024-10-14): `USDC -100` → `fcbBTC +0.00150267`. Priceable from the USDC side.
- Stake `0xb38998d5…` (2024-10-19): `fcbBTC -0.00150267` → `pfcbBTC +1.50267E-13`. Both exotic → fails.
  Has a manual override (`fcbBTC @ 61000.2196…`, note: "Copied from projected acquisition lot").
- Exit `0x7a391403…` (2024-10-20): reverses it. **This is what is failing right now.**

**UNI-V2 (FOX/ETH Uniswap V2 pool)** — `addLiquidityETH` → `stake` → `exit` → `restake` → `exit`
→ `removeLiquidityETH`, 2021-07 to 2022-07. Five events carry manual UNI-V2 overrides of mixed
provenance: two copied from projected lots, one hand-guessed with no note, two derived from
Etherscan USD values.

**RONIN Coinbase course rewards** — five one-sided receive events on 2024-06-15, plus an INTERNAL
correction that sells the residual for ETH. Overrides on the receives were hand-derived from the
later sale.

## What the investigation established

All of this is verified against the local DBs and raw Moralis payloads.

### 1. Intermediate rates cancel — the operator's instinct was right

For a **two-sided** event, the derived rate appears as both a disposal proceed and an acquisition
cost. It telescopes out of the chain total. Verified on fcbBTC by sweeping the exit rate from
€1 to €999,999 per fcbBTC: the total chain P&L is **€4.2669 every time**, equal to
`V3 - C0` (the cbBTC-priced exit minus the USDC-priced entry).

**Consequence: for two-sided events the rate does not need to be good, only consistent.**
Adjacency, or any consistent number, is sufficient. Staleness genuinely does not matter.

### 2. …but only when the hop *balances*

The cancellation requires the value to leave and re-enter through the same event.

- **fcbBTC satisfies this** because `pfcbBTC` is a real receipt token in the wallet.
- **The FOX farm does not.** The stake is a one-sided disposal (gas leg only) and the exit,
  months later, is a one-sided acquisition. UNI-V2 vanishes from the ledger in between. The two
  ends get priced independently and the difference never telescopes away.

Measured on the real persisted lots:

```
net UNI-V2 P&L as booked : EUR  -50.99
endpoint-only (correct)  : EUR -127.45
phantom leak             : EUR  +76.46
```

### 3. One-sided vs two-sided is the whole safety story

This falls straight out of (1) and (2), and it is the single most useful distinction found:

- **Two-sided event** — the rate cancels. Auto-resolve at any time distance, no review needed.
- **One-sided event** (airdrop, reward, untokenized stake) — no counterparty leg. The rate lands
  **in full, permanently**, in the income or gain line. Nothing cancels. Needs review.

### 4. `pfcbBTC` is not an exotic asset — it is a decimals artifact

From the raw Moralis payload for the stake tx:

```
fcbBTC   value=150267  decimals=8    dir=send
pfcbBTC  value=150267  decimals=18   dir=receive
```

**Same raw integer.** The Harvest PotPool mints 1:1 in raw units; the two tokens differ only in
declared decimals. `pfcbBTC` has no market and no independent value. The persisted lot reads
`cost_per_unit = 610,002,196,090,958.09 EUR/unit`, which is the model reporting that it is pricing
a unit that does not exist. The total value is right; the unit rate is meaningless.

### 5. `fcbBTC` is three different contracts

```
BASE 0xc5dc397b1db51da30dc9f3ac7084bbba1efbe249  FARM_cbBTC  dec=8   (2024-10 -> 2024-12)
BASE 0x52539e9c0ec50eaeee7d0c518f88c066209090cb  FARM_cbBTC  dec=8   (2024-12 -> 2025-01)
BASE 0xcafb01ab827b6d57ed17fc1db6091e094ef6a1d5  FARM_cbBTC  dec=8   (2025-01 -> 2025-01)
pfcbBTC: BASE 0x0950314900287c5192dd8f0d94d27261ba255927  dec=18
```

Three separate Harvest vaults, each with its own share price, collapsed into one `asset_id`
because `erc20_asset_id` keys assets by **symbol**. 59 of 545 symbols in the cache are backed
by more than one contract. **Decided: out of scope.** For total P&L this washes out (see 1).
Recorded here because it explains why the fcbBTC/cbBTC redemption ratio is non-monotonic, and
because it will matter if a holding-period rule is ever implemented.

## Decisions taken (do not relitigate)

- **Stake/unstake stays a taxable disposal + acquisition.** A receipt token is a different token.
  An earlier proposal to net these to zero in phase 1 was **rejected** on tax grounds.
- **Intermediate rate precision does not matter** for two-sided events. Proven. Do not add
  staleness limits, max time distances, or interpolation for these.
- **RONIN handling is correct.** Token received, taxed as income at receipt, sold minutes later
  at the same rate, no further gain. Right total.
- **FOX is mismapped in `cmc_asset_map.json`** (`"FOX": 1381` is a different coin; the pool's
  50/50 reserve invariant pins FOX at ~$0.80 on 2021-07-15 against CMC's $0.0127). This
  understates ~€280 of 2021/2022 **income**. **Decided: accept it.** Small, five years old.
  Not part of this task.
- **NEU is a separate bug — parked.** The 2021-05-13 Neufund redemption (6,519 NEU → 7 ETH)
  gets mid-pointed by `_rebalance_known_rates` because ETH and NEU are both `MARKET` tier, so
  the 7 ETH lot is booked at €1,654.85 against a €3,091.00 market. Different trigger (price
  *present* but divergent), different code path, different fix (rank within `MARKET`). Does not
  affect this task's design. **Own ticket.**

---

# Proposed solution

Resolve unpriceable events by borrowing a rate from the nearest event involving the same token
that *can* be priced by the existing standard rules.

Single-pass pipeline, unchanged in shape. When an event fails standard valuation, pause, run a
resolution subroutine, resume. No pre-pass.

## 1. Data model

`PriceOverride` gains one load-bearing field:

```python
class OverrideKind(StrEnum):
    MANUAL  = "MANUAL"    # a human deliberately set this
    DERIVED = "DERIVED"   # produced by anchor resolution

class PriceOverrideDraft(StrictBaseModel):
    event_origin: EventOrigin
    asset_id: AssetId
    rate_eur: Annotated[Decimal, Field(gt=0)]
    kind: OverrideKind = OverrideKind.MANUAL
    note: str | None = None
    # populated only when kind == DERIVED:
    derived_from: EventOrigin | None = None
    derived_from_timestamp: datetime | None = None
    derived_one_sided: bool = False
```

`kind` **must be a real column**, not something parsed out of `note`. It is what enforces the
"never anchor on a derived rate" invariant.

The existing unique constraint `(origin_location, origin_external_id, asset_id)` still holds.
A `MANUAL` and a `DERIVED` row can never collide, because the resolver only writes for assets
that have no override at all.

## 2. Lifecycle: derived rows are regenerated every run

This is the key decision. It makes "omit derived rates when finding anchors" and "remove them
for recalculation" **structural** rather than rules someone has to remember.

```
stage ACQUISITION_DISPOSAL:
    manual = load_overrides(kind=MANUAL)          # DERIVED rows are NOT loaded
    validate_overrides(corrected_events, manual)

    derived = []
    projection = project(corrected_events, overrides=manual, sink=derived.append)

    price_override_repo.replace_derived(derived)   # clear-then-write
    projection_repo.replace(projection)
```

Because only `MANUAL` overrides are loaded into the run, **the resolver structurally cannot
anchor on a derived rate.**

Consequences:

- **No staleness.** Recomputed from current data every run. Cannot shadow a price that later
  becomes available (the trap the existing RONIN/RNDR overrides are in — `_rate_in_base_currency`
  checks overrides *before* the provider).
- **Fully auditable.** Real rows, visible in DB and UI, carrying their provenance.
- **Operator can pin a value by editing it**, which flips `kind` to `MANUAL`. From then on it is
  respected, never regenerated, and becomes anchor-eligible.

Clear-then-write matches what `WalletBalanceRepository` and
`AcquisitionDisposalProjectionRepository` already do.

## 3. Definitions

- **Unknown set `U`** — non-fee projected assets with no rate from `manual` and none from the
  price provider.
- **One-sided event** — all non-fee projected residual groups carry the same sign. Fee legs never
  count. No opposing value, so remainder solving is impossible.
- **Anchor** — a `(rate, event_origin, timestamp)` for an asset, taken from an event that
  `value_projected_event` prices using **standard rules and `manual` overrides only**.

## 4. Main loop

```python
for event in events:                                    # Sequence, chronological
    projected = project_event_quantities(event)
    try:
        prices = value_projected_event(projected, timestamp=event.timestamp,
                                       price_provider=pp, overrides=manual_for(event))
    except AcquisitionDisposalValuationError:
        prices = resolve_by_anchor(projected, event, events, pp, manual, sink)
        if prices is None:
            failures.append(...)                        # collect, do not raise
            continue                                    # skip FIFO for this event
    match_event_fifo(projected, prices, ...)

if failures:
    raise AcquisitionDisposalValuationError(all_failures)   # one report, not first-fail
```

Collecting failures instead of dying on the first ends the rerun-whack-a-mole. The partial
projection is already documented as debug-only output, so degraded FIFO after a failure is
consistent with existing semantics.

`project()` currently takes `events: Iterable[LedgerEvent]`; tighten to `Sequence` (the caller
already passes a list).

## 5. `resolve_by_anchor`

```python
def resolve_by_anchor(projected, event, all_events, pp, manual, sink):
    U = [g.asset_id for g in projected.non_fee_groups
         if no rate from manual[event] and pp.rate(g.asset_id, EUR, event.timestamp) is None]

    anchors    = {a: find_anchor(a, event, all_events, pp, manual) for a in U}
    unanchored = [a for a in U if anchors[a] is None]
    one_sided  = all groups in projected.non_fee_groups have the same sign

    if len(unanchored) == 0:
        inject = {a: anchors[a].rate for a in U}
    elif len(unanchored) == 1 and not one_sided:
        inject = {a: anchors[a].rate for a in U if anchors[a]}   # last one is remainder-solved
    else:
        return None                                              # genuinely nothing to go on

    for a, rate in inject.items():
        sink(PriceOverrideDraft(
            event_origin=event.event_origin, asset_id=a, rate_eur=rate,
            kind=DERIVED,
            derived_from=anchors[a].origin,
            derived_from_timestamp=anchors[a].timestamp,
            derived_one_sided=one_sided,
            note=f"Derived from {anchors[a].origin} ({anchors[a].delta_human}). "
                 + ("ONE-SIDED: this rate does not cancel through the chain — review."
                    if one_sided else "")))

    return value_projected_event(projected, timestamp=event.timestamp, price_provider=pp,
                                 overrides=manual_for(event) | inject)
```

The final line re-invokes the **existing** valuator with a richer overrides map.
`_rate_in_base_currency` picks the injected rates up before hitting the provider, and
unknown-detection, remainder solving, tier anchoring and rebalancing all run unchanged.

**`valuation.py` needs no edits.**

Only *injected* anchor rates are persisted. Remainder-solved rates are a consequence of the
event and are not written out.

## 6. `find_anchor`

```python
def find_anchor(asset, event, all_events, pp, manual):
    candidates = [e for e in all_events
                  if e.event_origin != event.event_origin
                  and asset in {l.asset_id for l in e.legs if not l.is_fee}]

    candidates.sort(key=lambda e: (abs(e.timestamp - event.timestamp),   # nearest first
                                   e.timestamp,                          # deterministic tiebreak
                                   e.event_origin.location,
                                   e.event_origin.external_id))

    for c in candidates:
        rates = try_value_standard(c, pp, manual)     # memoized; pure function of the event
        if rates is not None and asset in rates:
            return Anchor(rates[asset], c.event_origin, c.timestamp,
                          c.timestamp - event.timestamp)
    return None
```

`try_value_standard` calls `value_projected_event` and swallows the valuation error. It **never**
calls `resolve_by_anchor` — that is the whole safety property. No recursion, so termination is
trivial. It is a pure function of the event, so memoise on `event_origin`.

Anchors may be in the **past or the future**; nearest wins. (One real case reaches 122 days
forward.) The tiebreak matters: without it, two equidistant candidates make the result depend on
list order.

## 7. Decision rule

| `unanchored` | event | action |
|---|---|---|
| 0 | two-sided | inject all anchors; rebalance meets in the middle |
| 0 | one-sided | inject all anchors; `_rebalance_known_rates` returns early (`valuation.py:152`, `disposal_total == 0`), so each asset keeps its own rate and nothing drags anything |
| 1 | two-sided | inject the anchors; the unanchored asset is **remainder-solved exactly** |
| 1 | one-sided | **fail** — no opposing value to solve against |
| ≥2 | either | **fail** — genuinely nothing to approximate from |

Failing only fires when there is truly no information. Those events still need a hand-authored
`MANUAL` override.

## 8. Invariants

1. **Anchors come only from standard valuation.** Enforced structurally — `DERIVED` rows are
   never loaded into the run.
2. **Anchor search never recurses.** No compounding, no circularity, no order-dependence.
3. **The resolver never overwrites a `MANUAL` override.** It only writes for assets with no rate.
4. **Derived rates are regenerated every run.** They cannot go stale or shadow a real price.
5. **One-sided derivations are flagged.** That flag is the operator's review queue.

## 9. Expected outcome against the real data

| event | U | anchor | Δt | branch | result |
|---|---|---|---|---|---|
| fcbBTC entry `0x797d` | {fcbBTC} | — | — | standard | **anchor** 61,000.22 |
| fcbBTC stake `0xb389` | {fcbBTC, pfcbBTC} | `0x3730` | 1.3d ahead | 1 unanchored, two-sided | fcbBTC 63,839.76; pfcbBTC solved |
| fcbBTC exit `0x7a39` **(failing now)** | {fcbBTC, pfcbBTC} | `0x3730` | **94 s** ahead | 1 unanchored, two-sided | fcbBTC 63,839.76; pfcbBTC solved |
| fcbBTC withdraw `0x3730` | {fcbBTC} | — | — | standard | **anchor** 63,839.76 |
| UNI-V2 addLiq `0x58c7` | {UNI-V2} | — | — | standard | **anchor** 36.600074986… |
| UNI-V2 stake `0x7a46` | {UNI-V2} | `0x58c7` | 2m33s | 0 unanchored, one-sided | **reproduces the existing override bit-for-bit** |
| UNI-V2 stake `0x3141` | {UNI-V2} | `0x178c` | 2m55s | 0 unanchored, one-sided | **bit-for-bit** |
| UNI-V2 exit `0x5343` | {UNI-V2} | `0x178c` | **86d back** | 0 unanchored, one-sided | 43.30 — overrules the hand-guessed 19.997, ⚠ flagged |
| UNI-V2 restake `0x6da4` | {UNI-V2} | `0xdd76` | **122d ahead** | 0 unanchored, one-sided | 10.55 — overrules the Etherscan 21.257, ⚠ flagged |
| UNI-V2 exit `0x8b9c` | {UNI-V2} | `0xdd76` | 3m17s | 0 unanchored, one-sided | 10.55 — overrules the Etherscan 22.741, ⚠ flagged |
| UNI-V2 removeLiq `0xdd76` | {UNI-V2} | — | — | standard | **anchor** 10.547835673… |
| RONIN × 5 receives | {RONIN} | `INTERNAL:08a2c4d4` | 2–4 min | 0 unanchored, one-sided | **reproduces the existing overrides exactly** |

Every currently-failing event resolves. Every good hand override is reproduced to the last digit.
The three values that were least defensible get overruled **and flagged**, so they are visible
rather than silently trusted.

Once this works, the existing manual overrides for fcbBTC, UNI-V2 and RONIN can be deleted —
the algorithm regenerates equivalents (or better ones) as `DERIVED`.

## 10. Known residual — the untokenized-stake phantom

The four one-sided UNI-V2 events still carry the ~€76 phantom described in "What the
investigation established (2)". Adjacency cannot fix it: the FOX farm issues no receipt token,
so there is nothing tying the two ends of the hop together, and no price strategy can invent one.

`derived_one_sided` surfaces these rather than hiding them.

**The real fix, deferred:** synthesise the missing receipt token. The FOX farm is a clean 1:1
non-rebasing stake (`3.774330133219511198 + 0.888967631393636005 = 4.663297764613147203` staked in,
exactly `4.663297764613147203` out). Give the staked position a synthetic asset, acquired at stake
and disposed at exit. Then every hop is two-sided, every rate telescopes, and the total becomes
exact — for *any* rate the resolver picks. It also keeps stake/unstake as taxable
disposals/acquisitions, which is the required tax treatment.

This can land later **without changing any of the algorithm above** — those events simply stop
being one-sided.

## 11. Suggested order of work

1. `OverrideKind` on `PriceOverride` + DB migration + `replace_derived()` repo method.
2. `find_anchor` + `try_value_standard` (memoised) + `resolve_by_anchor`.
3. Wire the `try/except` into `AcquisitionDisposalProjector.project()`; `Iterable` → `Sequence`.
4. Collect-all-failures instead of first-fail.
5. Surface `kind`, `derived_from` and `derived_one_sided` through the API/UI so the review queue
   is visible.
6. Delete the now-redundant manual overrides for fcbBTC / UNI-V2 / RONIN and confirm the run
   reaches `COMPLETED`.

Deferred, separate tickets: synthetic receipt tokens for untokenized stakes; `MARKET`-tier
ranking (the NEU bug); asset identity by contract address.
