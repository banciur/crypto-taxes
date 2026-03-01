import { cache } from "react";

import { getAccounts } from "@/api/accounts";

export const getAccountNamesById = cache(
  async (): Promise<Map<string, string>> => {
    const accounts = await getAccounts();
    return new Map(
      accounts.map((account) => [account.accountChainId, account.name]),
    );
  },
);
