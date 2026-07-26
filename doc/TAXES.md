# Tax Model

This document describes the target tax model and rationale for the `TAX_COMPUTATION` stage.

> **Note:** The legal interpretations here come from internal research supported by AI tools. Confirm them against the BMF guidance or a Steuerberater before relying on the figures.

## Purpose

The acquisition/disposal projection says what was acquired and disposed, in what quantity, and at what EUR value. It does not say which of those movements German income tax reaches.

Tax logic answers three further questions:

- which movements are taxable at all
- under which paragraph, since the paragraphs have different rates, allowances and loss rules
- in which calendar year

## Scope

The stage turns acquisition lots and disposal links into `TaxEvent`s, one per taxable movement. It reads corrected ledger events as well, because classifying a receipt depends on the shape of the event that produced it rather than on the lot alone.

## Tax Categories

Two categories cover everything the ledger produces.

**`PRIVATE_SALE` — §23 EStG, *privates Veräußerungsgeschäft*.** Disposing of an asset held inside the one-year speculation period: selling, swapping, spending, or paying a fee in it. The amount is a signed gain, proceeds minus cost basis, so a disposal at a loss carries a negative amount.

**`OTHER_INCOME` — §22 Nr. 3 EStG, *sonstige Einkünfte*.** Receiving an asset in return for an activity: staking rewards, protocol incentives, airdrops earned by participation. The amount is the asset's EUR value at receipt, which is also its cost basis for a later `PRIVATE_SALE`.

Both feed ordinary taxable income at the personal marginal rate. They are separate baskets: each has its own Freigrenze, and losses in one never offset income in the other.

§20 EStG, capital income, does not arise from ledger activity. It requires a *Kapitalforderung*, a claim for repayment of money, and lending crypto is a loan of a thing rather than of money. Crypto lending and staking yields therefore fall under §22 Nr. 3.

## The Speculation Period

A disposal is taxable when it happens no more than one year after the acquisition of the lot it consumes. §23 Abs. 3 S. 5 EStG measures the period under §108 AO with §§187–188 BGB, so it is compared on calendar dates rather than on elapsed time: a disposal is inside the period up to and including the anniversary of the lot's acquisition date, and outside it from the day after. Dates are read in Europe/Berlin, since German tax reckons in German days.

A disposal outside the period produces no `TaxEvent`. It remains in the projection, where the summary page and reconciliation read it.

The period applies per lot fragment. One disposal leg funded by three lots is tested three times, and the fragments can fall on either side of the line.

## Classifying Receipts

An acquisition lot produces an `OTHER_INCOME` event when its source event was a one-sided receipt:

```
non-fee legs -> net per asset -> flip sign for liability assets
  every surviving net positive -> receipt
  otherwise                    -> not a receipt
```

Fiat legs count as counterparts like any other asset, so a fiat purchase is not a receipt. A fiat-only event such as a bank deposit reads as one, which is never consulted because fiat opens no FIFO lot.

Staking rewards reach the ledger in two shapes: a separate reward token arriving, and the balance of a held token growing. Both are receipts. The reward is consideration for staking, so each one recognises income at its value at the moment it lands.

Every receipt is treated as taxable income. Whether a particular receipt was earned by an activity — a *Leistung* — turns on facts outside the ledger: what a protocol announced, and what was done to qualify for it. An airdrop that arrives with nothing given in return is arguably not income at receipt, but the ledger cannot see the difference, so the stage acts on the shape of the event.

## Debt Tokens

A debt token is an asset whose EUR value is the underlying's price negated. Borrowing opens a negative-cost lot beside the lot for the asset received; repaying disposes both.

The consequence is that the debt's gain moves opposite to the position it financed. Borrowing an asset, deploying it, and repaying nets to roughly zero, because a fall in the underlying's price is a gain on the debt and a loss on what the borrowing bought. Removing the debt leg would leave the financed position's gain standing alone.

The *Fremdwährungsdarlehen* treatment is the closest established analogy: repaying a foreign-currency loan after the currency moved can produce a §23 gain, because the currency is the asset.

Two consequences worth knowing:

- Interest leaves no trace. The extra quantity handed back at repayment is disposed at the price it was acquired at, so it nets to zero rather than appearing as a cost.
- A rolled debt and the position it finances can fall on opposite sides of the one-year line, which taxes the gain while stranding the offsetting loss.

## Yearly Totals

Per calendar year, per category.

**§23.** Net gains against losses within the private-sale basket. Losses offset only §23 gains; they carry back one year and forward indefinitely under §10d. Apply the Freigrenze to the year's total gain: €600 through 2023, €1,000 from 2024. It is a Freigrenze rather than a Freibetrag, so a total below the threshold is free and a total at or above it is taxable in full.

**§22 Nr. 3.** Sum the receipts and apply the €256 Freigrenze the same way.

The two thresholds are independent and do not combine.

## Questions Requiring Professional Confirmation

- Whether a debt token is a taxable position in its own right, or whether borrowing and repaying should stay outside §23.
- Whether borrowing interest is deductible, and against what.
- Whether a fee paid in an asset stays a standalone §23 disposal only, or whether its EUR value is also *Werbungskosten* of the transaction it belongs to and reduces that transaction's gain under §23 Abs. 3 S. 1.
- Which airdrops were earned by a *Leistung*, decided per airdrop rather than per asset, and how one that was not is treated on later disposal.
