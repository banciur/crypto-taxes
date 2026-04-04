import { getFromApi } from "@/api/core";
import type { WalletProjectionState } from "@/types/walletProjection";

export const getWalletProjection = async (): Promise<WalletProjectionState> =>
  getFromApi<WalletProjectionState>("/wallet-projection");
