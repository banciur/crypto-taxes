"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";

type AccountNamesById = Record<string, string>;
type GetAccountName = (accountChainId: string) => string;

const AccountNamesContext = createContext<AccountNamesById | undefined>(
  undefined,
);

export function AccountNamesProvider({
  accountNamesById,
  children,
}: {
  accountNamesById: AccountNamesById;
  children: ReactNode;
}) {
  return (
    <AccountNamesContext.Provider value={accountNamesById}>
      {children}
    </AccountNamesContext.Provider>
  );
}

export function useAccountNames(): AccountNamesById {
  const context = useContext(AccountNamesContext);

  if (!context) {
    throw new Error("useAccountNames must be used within AccountNamesProvider");
  }

  return context;
}

export function useAccountNameResolver(): GetAccountName {
  const accountNamesById = useAccountNames();

  return useMemo(
    () => (accountChainId: string) =>
      accountNamesById[accountChainId] ?? accountChainId,
    [accountNamesById],
  );
}
