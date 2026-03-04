import "server-only";

import { cache } from "react";

import { getAccounts } from "@/api/accounts";

export const loadAccountNamesById = cache(
  async (): Promise<Record<string, string>> => {
    const accounts = await getAccounts();

    return Object.fromEntries(
      accounts.map((account) => [account.accountChainId, account.name]),
    );
  },
);
