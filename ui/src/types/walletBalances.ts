import type { AccountChainId, AssetId, DecimalString } from "@/types/events";

export type WalletBalance = {
  accountChainId: AccountChainId;
  assetId: AssetId;
  balance: DecimalString;
};
