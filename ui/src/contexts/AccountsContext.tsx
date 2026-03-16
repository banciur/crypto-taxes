"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { Account } from "@/types/events";

const AccountsContext = createContext<Account[] | undefined>(undefined);

type AccountsProviderProps = {
  accounts: Account[];
  children: ReactNode;
};

export function AccountsProvider({
  accounts,
  children,
}: AccountsProviderProps) {
  return (
    <AccountsContext.Provider value={accounts}>
      {children}
    </AccountsContext.Provider>
  );
}

export function useAccounts(): Account[] {
  const context = useContext(AccountsContext);
  if (!context) {
    throw new Error("useAccounts must be used within AccountsProvider");
  }

  return context;
}
