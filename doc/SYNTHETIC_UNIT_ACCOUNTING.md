# Synthetic Unit Accounting

## Purpose

This document describes an accounting model for positions represented by a mutable NFT, such as a Uniswap v3 liquidity position. The model allows one NFT to receive multiple increases and partial withdrawals while retaining separate acquisition dates and EUR cost bases for FIFO matching.

This is an accounting model, not a settled interpretation of German tax law. It assumes that contributing assets acquire an economic position and that withdrawing principal disposes of part of that position.

## Position Model

The NFT identifies the position but is not treated as a single indivisible inventory unit. The position contains a quantity of homogeneous units. These can be native protocol liquidity units or synthetic units created by the accounting system.

For a position with current principal value `V` and `Q` outstanding units:

```text
unit price = V / Q
```

Changes in market value change the unit price, not the number of units. Accrued fees are excluded from principal value and accounted for separately.

### Mint

The initial principal value is the EUR value of the assets contributed:

```text
V = EUR value of contributed assets
Q = protocol liquidity, when available
```

When the protocol does not expose a useful unit quantity, the initial synthetic quantity can be set equal to the initial EUR value. This gives an initial unit price of EUR 1 without affecting later calculations.

The mint creates the first FIFO lot with the mint timestamp, `Q` units, and cost basis `V`.

### Increase

An increase worth `A` acquires units at the position's unit price immediately before the increase:

```text
added units = A / unit price before increase
new position value = V + A
new unit quantity = Q + added units
```

The added units form a new FIFO lot with their own acquisition timestamp and EUR cost basis `A`. Issuing them at the pre-increase unit price prevents dilution of the existing lots.

### Partial Withdrawal

A principal withdrawal worth `D` disposes of units at the position's unit price immediately before the withdrawal:

```text
removed units = D / unit price before withdrawal
new position value = V - D
new unit quantity = Q - removed units
```

The removed units consume acquisition lots through FIFO. The disposal result is:

```text
gain or loss = D - FIFO cost basis - attributable costs
```

The returned assets receive new acquisition timestamps and EUR cost bases equal to their respective values at withdrawal.

### Full Withdrawal

A full withdrawal disposes of every remaining unit and consumes all remaining position basis. An empty NFT has no remaining position value or basis. Burning the empty NFT is an administrative operation rather than another economic disposal.

## Pure Uniswap V3 Positions

For a direct Uniswap v3 position, the value of a liquidity change is available from the actual token amounts entering or leaving the position. The following assumptions apply:

- both assets have known EUR prices at the operation timestamp;
- the token amounts used by the operation follow the current internal token ratio of the position;
- the NFT retains one fixed pool and tick range;
- fees are excluded from the principal amounts.

For token amounts `amount0` and `amount1`:

```text
change value = amount0 * EUR price0 + amount1 * EUR price1
```

Uniswap's native liquidity `L` is the preferred unit quantity. For a fixed range, token amounts are linear in `L`, so all liquidity units in the NFT have the same token composition at a given pool price. Mint, increase, and decrease operations expose a liquidity delta `delta_L`.

An increase can therefore derive the current unit price and the value of the existing position without independently reconstructing all token balances inside the NFT:

```text
unit price = increase value / delta_L
existing principal value = L_before * unit price
```

A decrease consumes exactly `delta_L` through FIFO. Its EUR proceeds come from the actual principal amounts returned. The changing token0/token1 ratio is reflected in those amounts and in the protocol's liquidity calculation.

## Complex Atomic Flows

Aggregators can accept one asset, perform internal trades, and add the resulting assets to a different pool in one transaction. When the final token amounts, protocol units, or reliable position value cannot be recovered, the last known post-operation NFT value can be carried forward as an estimate of the value before the next operation.

For an increase, the EUR value of the asset given to the aggregator is used as the new lot's cost basis. The last known position value supplies the estimated unit price:

```text
estimated unit price = previous position value / current units
estimated added units = input EUR value / estimated unit price
```

For a withdrawal, the EUR value of the assets received supplies the disposal proceeds. Units are estimated using the carried-forward unit price when no protocol quantity or reliable current position value is available.

This carry-forward method assumes that the NFT value has not changed since the previous operation. Market movements, pool rebalancing, slippage, aggregator fees, and unobserved compounding violate that assumption. The resulting unit quantity can therefore be wrong even when the contribution or withdrawal value is known.

Carry-forward valuations must be marked as estimates and remain replaceable when better historical data becomes available. The preferred recovery order is:

1. protocol liquidity or vault-share deltas;
2. actual final pool token amounts from transaction events;
3. historical pool state and protocol formulas;
4. an externally reported NFT or vault value;
5. the previous-operation carry-forward estimate.

## FIFO and the One-Year Rule

Each mint or increase creates a dated unit lot. A partial withdrawal consumes the oldest open units first. This determines both the allocated cost basis and which acquisition dates are tested against the one-year holding period.

If every lot is taxable, every operation occurs in the same tax period, and the position is fully withdrawn, unit-allocation errors do not change the total lifetime result:

```text
total gain or loss = total withdrawals - total contributions - attributable costs
```

They can still assign gains to the wrong withdrawal. The allocation becomes materially important when:

- the position remains open at year-end;
- operations span tax years;
- some lots are older than one year and others are not;
- taxable and non-taxable withdrawals are mixed;
- fees or rewards are included in principal value.

## Example

An NFT is minted with EUR 1,000. The initial synthetic quantity is 1,000 units at EUR 1 per unit. Its principal later becomes worth EUR 1,200, so the unit price is EUR 1.20.

An increase of EUR 350 acquires:

```text
EUR 350 / EUR 1.20 = 291.666667 units
```

After the increase, the position contains 1,291.666667 units worth EUR 1,550. The unit price remains EUR 1.20, so the existing position was not diluted. A later partial withdrawal converts its EUR principal value to units at the then-current unit price and consumes those units through FIFO.

## Protocol Boundaries

The units are homogeneous only while they represent the same economic position. A change of pool, tick range, strategy, or ownership wrapper closes the old unit series and opens a new one unless the protocol itself supplies a stable share unit across the change.

For vault protocols such as Beefy, the user's vault shares are normally the relevant accounting units. The vault's underlying NFT positions belong to the vault and can be rebalanced independently of the user's share lots.
