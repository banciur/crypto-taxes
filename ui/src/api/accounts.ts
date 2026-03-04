import { getFromApi } from "@/api/core";
import type { Account } from "@/types/events";

export const getAccounts = async (): Promise<Account[]> =>
  getFromApi<Account[]>("/accounts");
