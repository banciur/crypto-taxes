# Wealth Tracking Model (draft)

- **Point-in-time net worth**: base-currency cash plus market value of all holdings. Capture periodic snapshots (daily/weekly) with quantities, prices used, and totals.
- **Flow view per period (day/week/month)**:
  - External cash flows: deposits/withdrawals vs the outside world (crossing the `outside` boundary only).
  - Income: staking/LP rewards/airdrops/etc. at fair market value when received.
  - Realized P&L: proceeds minus cost basis on disposals (trades, swaps, spending, LP exits, gas disposals); reinvestments are a disposal plus a new acquisition.
  - Fees/interest: explicit drags if not already in disposal legs.
  - Taxes: accrued tax liability for the period as a drag.
  - Unrealized P&L: price drift on open positions; stops for a position once it is disposed and can be derived as the reconciliation term between snapshots.
- **Reconciliation**: change in net worth = cash flows + income + realized P&L − fees/taxes + unrealized P&L.
- **Optional metrics**:
  - Time-weighted return (TWR) to strip timing of deposits/withdrawals.
  - Money-weighted return (IRR/XIRR) to include cash flow timing.
  - Breakdowns by asset and by source (trading vs income vs fees).
- **Valuation cadence**: use consistent end-of-day pricing; record price sources/FX used for reproducibility.
- **Weekly cadence**: take an end-of-week snapshot of holdings in EUR (with recorded prices/sources), classify flows per the buckets above, and keep per-token detail for income while retaining EUR roll-ups. Unrealized is the price drift between snapshots; it stops on disposal. Future: add TWR/IRR and risk metrics here when ready.
