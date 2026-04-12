// This file is completely vibed and I didn't read it.
"use client";

import type {
  WalletProjectionState,
  WalletProjectionStatus,
} from "@/types/walletProjection";
import { WalletProjectionBalancesTable } from "./WalletProjectionBalancesTable";
import { WalletProjectionIssueList } from "./WalletProjectionIssueList";
import styles from "./WalletProjectionPanel.module.css";

type WalletProjectionPanelProps = {
  state: WalletProjectionState;
};

const STATUS_META: Record<
  WalletProjectionStatus,
  {
    toneClassName: string;
    description: string;
  }
> = {
  NOT_RUN: {
    toneClassName: "text-muted",
    description:
      "No wallet projection snapshot has been persisted yet. Re-run the backend pipeline after correction changes to populate this view.",
  },
  COMPLETED: {
    toneClassName: "text-success",
    description:
      "Wallet projection finished without blocking balance issues. Balances below reflect the current corrected-ledger snapshot.",
  },
  FAILED: {
    toneClassName: "text-danger",
    description:
      "Wallet projection stopped at the first blocking balance failure. Issues below describe the failed event, while balances remain the last fully applied snapshot.",
  },
};

export function WalletProjectionPanel({ state }: WalletProjectionPanelProps) {
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
          <WalletProjectionIssueList issues={state.issues} />
        </section>
      )}

      {state.status !== "NOT_RUN" && (
        <section>
          <div className="small text-uppercase text-muted mb-2">Balances</div>
          <WalletProjectionBalancesTable balances={state.balances} />
        </section>
      )}
    </div>
  );
}
