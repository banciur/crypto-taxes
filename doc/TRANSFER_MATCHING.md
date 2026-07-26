# Transfer Matching

This document describes how a movement of assets between two owned venues can be recognised and merged
into a single ledger event. The work is currently done by hand through the correction flow; the model
below is what an automated proposal step would implement.

## Purpose

Quantity projection nets legs within one event. A movement between two owned venues does not arrive as one
event: the sending venue and the receiving venue are separate sources, so the movement imports as two
events with different `EventOrigin`s and nothing joins them.

Neither event can net. The send projects as a disposal of the full amount and the receive projects as an
acquisition of the same asset at market value on arrival.

The consequences are worse than a cosmetic duplication:

- The send consumes real acquisition lots and books proceeds against them.
- The receive opens a fresh lot dated to the arrival, discarding the original acquisition date.

The second one is what costs money. An asset held long enough to be exempt re-enters inventory with a
restarted holding period, so a later sale is reported as a taxable short-term gain even though the coins
were acquired years earlier. The error direction is always the same: it manufactures taxable gains out of
holdings that were not taxable.

## Scope

Two separable steps:

1. **Detection**: find pairs of events that describe one movement.
2. **Construction**: build the replacement correction that merges a confirmed pair.

Construction is deterministic and safe to automate. Detection is a heuristic and produces candidates for
confirmation, never an automatic rewrite. The reason is in "Why detection cannot be trusted alone" below.

## Detection

Candidates are drawn from *one-sided* events: those whose non-fee residuals all share one sign. This is
read directly from the projected event, so no new data has to be recorded at import time. A one-sided
negative event is a send candidate, a one-sided positive event a receive candidate.

A send and a receive form a candidate pair when all of the following hold:

- the same `asset_id` on both sides
- different `EventOrigin.location`, since one venue's movement nets within its own event
- the receive falls within a time window of the send
- the quantities agree within a tolerance, absorbing whatever fee was taken in transit

Pairing must be deterministic: iterate sends oldest first, take the first eligible receive, and consume
each receive at most once. Otherwise the same receive can be claimed by competing sends and the output
depends on iteration order.

A window of 48 hours and a tolerance of 3% are conservative starting values. Both trade recall for
precision, and precision is the one that matters, because a false pair deletes a real disposal.

## Why detection cannot be trusted alone

The heuristic is bounded in ways that cannot be fixed by loosening its parameters:

- **Asset-changing routes.** A bridge that delivers a wrapped or chain-local variant breaks the same-asset
  requirement.
- **Multi-hop routes.** Value that passes through an intermediate venue produces a chain of events, not a
  pair.
- **Split and aggregated movements.** One send answered by several receives, or the reverse, has no
  quantity that matches.
- **Slow credits.** A venue that credits days later falls outside any window short enough to stay precise.
- **Missing counterparts.** When one side was never imported — a venue no longer covered by an importer, a
  chain that is not synced — no pair exists to find. These are the dangerous ones: a receive with no
  visible send is shape-identical to income, and will be classified as such by anything that reasons from
  shape alone.

Loosening the window or tolerance to catch more of the first four increases false pairs, and a false pair
is not a cosmetic error. Merging two unrelated events erases a genuine disposal and a genuine acquisition
and silently changes the tax result.

So the output is a ranked candidate list. Ranking by the EUR value of the phantom disposal, and by the
short-term gain booked on lots the receive side created, puts the cases that change the tax number first.

## Construction

The merging correction claims both raw events as sources and replaces them with one event whose legs
describe the movement. The transferred asset gets a non-fee pair, and the difference between what left and
what arrived — the fee taken in transit, which no source reports as a fee — becomes an explicit fee leg.

Three cases determine where that fee sits and what the non-fee pair carries:

| Condition | Non-fee pair | Fee leg |
| --- | --- | --- |
| Destination credited more than was sent | sent on the source, credited on the destination | none |
| Destination is an exchange | sent, on both sides | on the destination |
| Otherwise | credited, on both sides | on the source |

The principle is that the fee leg belongs to the account that charged it, and the non-fee pair carries
whatever that account did not take.

An exchange charges a deposit fee after crediting the full incoming amount, so the pair is gross and the
fee lands on the exchange. An exchange withdrawal fee and a bridge cut are both taken before the
destination sees anything, so the pair is net. For a withdrawal the source is the exchange that charged it.
For a bridge neither account charged it, and the source is chosen because the source demonstrably held the
asset: a fee booked against a destination that acquired nothing in that event has no lots to consume under
per-wallet lot tracking.

The first case is not a fee at all. A venue that reports a credit larger than the amount sent is rounding
its own figure, and forcing the legs to cancel would debit the source more than actually left it. Each side
keeps its own reported figure, the legs do not cancel, and the dust projects as a small acquisition.

Two further rules make the result total:

- Every leg of either source event that is not part of the transferred pair carries through unchanged. Gas,
  and bridge fees paid in a native asset alongside the transferred one, are preserved rather than
  reclassified or absorbed.
- Legs that collide on `(account_chain_id, asset_id, is_fee)` merge. This is what keeps a gas fee and a
  transfer fee denominated in the same asset on the same account representable under the leg uniqueness
  invariant.

## Validation

A merging correction must not change any balance. The check is exact:

> For every `(account_chain_id, asset_id)`, the correction's legs must sum to what the raw events it claims
> summed to.

This is verifiable before the correction is stored, and it is the check that catches the characteristic
failure: counting the transfer fee twice, once implicitly as the gap between non-fee legs that do not
cancel and once again as an explicit fee leg. The result is an account debited more than reality, which
surfaces much later as a negative balance at an unrelated event.

Wallet projection cannot catch this at authoring time. It nets an event's legs per account before
validating, so the leg decomposition is invisible to it, and an over-debit only fails once the balance
actually runs out.

## Consequences of the Model

- A movement between owned venues creates no acquisition lot and no disposal.
- The original acquisition date survives, so the holding period is measured from when the asset was really
  acquired.
- The transfer cost stays explicit through `is_fee=True` and remains separately identifiable downstream.
- Balances are unchanged by construction, which is what makes the correction safe to generate mechanically
  once a pair is confirmed.
