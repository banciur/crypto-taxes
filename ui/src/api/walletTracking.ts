import { getFromApi } from "@/api/core";
import type { WalletTrackingState } from "@/types/walletTracking";

export const getWalletTracking = async (): Promise<WalletTrackingState> =>
  getFromApi<WalletTrackingState>("/wallet-tracking");
