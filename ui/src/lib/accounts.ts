import "server-only";

import { cache } from "react";

import { getAccounts } from "@/api/accounts";

// Another vibed unclear code. Fix it the moment that public api
// async loadAccounts sync getAccountName would have to change

type AccountsState = {
  accountNamesById: Map<string, string> | null;
  loadPromise: Promise<Map<string, string>> | null;
};

const getAccountsState = cache(
  (): AccountsState => ({
    accountNamesById: null,
    loadPromise: null,
  }),
);

const fetchAccountNamesById = async (): Promise<Map<string, string>> => {
  const accounts = await getAccounts();

  return new Map(
    accounts.map((account) => [account.accountChainId, account.name]),
  );
};

const getLoadedAccountNamesById = (): Map<string, string> => {
  const { accountNamesById } = getAccountsState();

  if (!accountNamesById) {
    throw new Error(
      "Accounts were not loaded for this request. Call loadAccounts() before reading account names.",
    );
  }

  return accountNamesById;
};

export const loadAccounts = async (): Promise<void> => {
  const state = getAccountsState();

  if (state.accountNamesById) {
    return;
  }

  if (!state.loadPromise) {
    state.loadPromise = fetchAccountNamesById();
  }

  state.accountNamesById = await state.loadPromise;
};

export const getAccountName = (accountChainId: string): string =>
  getLoadedAccountNamesById().get(accountChainId) ?? accountChainId;
