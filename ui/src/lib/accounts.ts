import "server-only";

import { cache } from "react";

import { getAccounts } from "@/api/accounts";
import type { Account } from "@/types/events";

export const loadAccounts = cache(
  async (): Promise<Account[]> => getAccounts(),
);

export const loadAccountNamesById = cache(
  async (): Promise<Record<string, string>> => {
    const accounts = await loadAccounts();

    return Object.fromEntries(
      accounts.map((account) => [account.accountChainId, account.name]),
    );
  },
);
