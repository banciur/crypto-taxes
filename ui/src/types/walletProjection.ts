import type {
  AccountChainId,
  AssetId,
  DecimalString,
  EventOrigin,
} from "@/types/events";

export type WalletProjectionStatus = "NOT_RUN" | "COMPLETED" | "FAILED";

export type WalletProjectionBalance = {
  accountChainId: AccountChainId;
  assetId: AssetId;
  balance: DecimalString;
};

export type WalletProjectionIssue = {
  event: EventOrigin;
  accountChainId: AccountChainId;
  assetId: AssetId;
  attemptedDelta: DecimalString;
  availableBalance: DecimalString;
  missingBalance: DecimalString;
};

export type WalletProjectionState = {
  status: WalletProjectionStatus;
  failedEvent: EventOrigin | null;
  issues: WalletProjectionIssue[];
  balances: WalletProjectionBalance[];
};
