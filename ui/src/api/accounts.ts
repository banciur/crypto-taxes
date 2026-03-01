import { getFromApi } from "@/api/core";

export type ApiAccount = {
  account_chain_id: string;
  name: string;
  chain: string;
  address: string;
  skip_sync: boolean;
};

export const getAccounts = async (): Promise<ApiAccount[]> =>
  getFromApi<ApiAccount[]>("/accounts");
