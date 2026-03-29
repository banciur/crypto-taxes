// This file is completely vibed and I didn't read it.
"use client";

import type {
  WalletTrackingState,
  WalletTrackingStatus,
} from "@/types/walletTracking";
import { WalletTrackingBalancesTable } from "./WalletTrackingBalancesTable";
import { WalletTrackingIssueList } from "./WalletTrackingIssueList";
import styles from "./WalletTrackingPanel.module.css";

type WalletTrackingPanelProps = {
  state: WalletTrackingState;
};

const STATUS_META: Record<
  WalletTrackingStatus,
  {
    toneClassName: string;
    description: string;
  }
> = {
  NOT_RUN: {
    toneClassName: "text-muted",
    description:
      "No wallet-tracking snapshot has been persisted yet. Re-run the backend pipeline after correction changes to populate this view.",
  },
  COMPLETED: {
    toneClassName: "text-success",
    description:
      "Wallet tracking finished without blocking balance issues. Balances below reflect the current corrected-ledger snapshot.",
  },
  FAILED: {
    toneClassName: "text-danger",
    description:
      "Wallet tracking stopped at the first blocking balance failure. Issues below describe the failed event, while balances remain the last fully applied snapshot.",
  },
};

export function WalletTrackingPanel({ state }: WalletTrackingPanelProps) {
  const statusMeta = STATUS_META[state.status];

  return (
    <div className={styles.panelCard}>
      <p className={`small mb-3 mt-3 ${statusMeta.toneClassName}`}>
        {statusMeta.description}
      </p>

      {state.status === "FAILED" && state.issues.length > 0 && (
        <section className="mb-4">
          <div className="small text-uppercase text-muted mb-2">
            Blocking issues
          </div>
          <WalletTrackingIssueList issues={state.issues} />
        </section>
      )}

      {state.status !== "NOT_RUN" && (
        <section>
          <div className="small text-uppercase text-muted mb-2">Balances</div>
          <WalletTrackingBalancesTable balances={state.balances} />
        </section>
      )}
    </div>
  );
}
