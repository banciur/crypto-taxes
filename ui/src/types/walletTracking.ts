import type {
  AccountChainId,
  AssetId,
  DecimalString,
  EventOrigin,
} from "@/types/events";

export type WalletTrackingStatus = "NOT_RUN" | "COMPLETED" | "FAILED";

export type WalletTrackingBalance = {
  accountChainId: AccountChainId;
  assetId: AssetId;
  balance: DecimalString;
};

export type WalletTrackingIssue = {
  event: EventOrigin;
  accountChainId: AccountChainId;
  assetId: AssetId;
  attemptedDelta: DecimalString;
  availableBalance: DecimalString;
  missingBalance: DecimalString;
};

export type WalletTrackingState = {
  status: WalletTrackingStatus;
  processedEventCount: number;
  lastAppliedEvent: EventOrigin | null;
  failedEvent: EventOrigin | null;
  issues: WalletTrackingIssue[];
  balances: WalletTrackingBalance[];
};
