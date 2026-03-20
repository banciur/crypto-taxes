"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";

import type { Account } from "@/types/events";

type AccountCatalog = {
  accounts: readonly Account[];
  resolveAccountName: (accountChainId: string) => string;
};

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
  const value = useMemo<AccountCatalog>(() => {
    const accountNamesById = Object.fromEntries(
      accounts.map((account) => [account.accountChainId, account.displayName]),
    );

    return {
      accounts,
      resolveAccountName: (accountChainId: string) =>
        accountNamesById[accountChainId] ?? accountChainId,
    };
  }, [accounts]);

  return (
    <AccountNamesContext.Provider value={value}>
      {children}
    </AccountNamesContext.Provider>
  );
}

export function useAccountNames(): AccountCatalog {
  const context = useContext(AccountNamesContext);

  if (!context) {
    throw new Error("useAccountNames must be used within AccountNamesProvider");
  }

  return context;
}
