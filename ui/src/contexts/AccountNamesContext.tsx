"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";

import type { Account } from "@/types/events";

type AccountCatalog = {
  accounts: readonly Account[];
  accountNamesById: Record<string, string>;
};
type GetAccountName = (accountChainId: string) => string;

const AccountNamesContext = createContext<AccountCatalog | undefined>(
  undefined,
);

export function AccountNamesProvider({
  accounts,
  children,
}: {
  accounts: Account[];
  children: ReactNode;
}) {
  const value = useMemo<AccountCatalog>(
    () => ({
      accounts,
      accountNamesById: Object.fromEntries(
        accounts.map((account) => [account.accountChainId, account.name]),
      ),
    }),
    [accounts],
  );

  return (
    <AccountNamesContext.Provider value={value}>
      {children}
    </AccountNamesContext.Provider>
  );
}

export function useAccounts(): readonly Account[] {
  const context = useContext(AccountNamesContext);

  if (!context) {
    throw new Error("useAccountNames must be used within AccountNamesProvider");
  }

  return context.accounts;
}

export function useAccountNames(): Record<string, string> {
  const context = useContext(AccountNamesContext);

  if (!context) {
    throw new Error("useAccountNames must be used within AccountNamesProvider");
  }

  return context.accountNamesById;
}

export function useAccountNameResolver(): GetAccountName {
  const accountNamesById = useAccountNames();

  return useMemo(
    () => (accountChainId: string) =>
      accountNamesById[accountChainId] ?? accountChainId,
    [accountNamesById],
  );
}
