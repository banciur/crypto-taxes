# Wealth Tracking Model (draft)

- **Point-in-time net worth**: base-currency cash plus market value of all holdings. Capture periodic snapshots (daily/weekly) with quantities, prices used, and totals.
- **Flow view per period (day/week/month)**:
  - External cash flows: deposits/withdrawals vs the outside world.
  - Income: staking/LP rewards/airdrops/etc. at fair market value when received.
  - Realized P&L: proceeds minus cost basis on disposals (trades, swaps, spending, LP exits); fees fold into this.
  - Fees/interest/taxes paid: explicit drags if not already in disposal legs.
  - Unrealized P&L: price drift on open positions; can be derived as the reconciliation term between snapshots.
- **Reconciliation**: change in net worth = cash flows + income + realized P&L − fees/taxes + unrealized P&L.
- **Optional metrics**:
  - Time-weighted return (TWR) to strip timing of deposits/withdrawals.
  - Money-weighted return (IRR/XIRR) to include cash flow timing.
  - Breakdowns by asset and by source (trading vs income vs fees).
- **Valuation cadence**: use consistent end-of-day pricing; record price sources/FX used for reproducibility.
