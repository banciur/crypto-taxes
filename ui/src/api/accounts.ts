import { getFromApi } from "@/api/core";

export type Account = {
  accountChainId: string;
  name: string;
  chain: string;
  address: string;
  skipSync: boolean;
};

export const getAccounts = async (): Promise<Account[]> =>
  getFromApi<Account[]>("/accounts");
