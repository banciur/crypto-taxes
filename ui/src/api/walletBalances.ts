import { getFromApi } from "@/api/core";
import type { WalletBalance } from "@/types/walletBalances";

export const getWalletBalances = async (): Promise<WalletBalance[]> =>
  getFromApi<WalletBalance[]>("/wallet-balances");
