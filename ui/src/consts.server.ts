import "server-only";

import {
  getAccounts,
  getCorrectedEvents,
  getRawEvents,
  getSeedEvents,
  type ApiAccount,
  type ApiLedgerEvent,
  type ApiLedgerLeg,
  type ApiSeedEvent,
} from "@/api/events";
import type { ColumnKey } from "@/consts";
import type { EventCardData, EventLeg } from "@/types/events";

type ColumnDefinition = {
  load: () => Promise<EventCardData[]>;
};

let accountNamesByIdPromise: Promise<Map<string, string>> | null = null;

const getAccountNamesById = async (): Promise<Map<string, string>> => {
  if (accountNamesByIdPromise) {
    return accountNamesByIdPromise;
  }
  accountNamesByIdPromise = getAccounts().then((accounts: ApiAccount[]) => {
    const map = new Map<string, string>();
    for (const account of accounts) {
      map.set(account.account_chain_id, account.name);
    }
    return map;
  });
  return accountNamesByIdPromise;
};

const mapLegs = (
  legs: ApiLedgerLeg[],
  accountNamesById: Map<string, string>,
): EventLeg[] =>
  legs.map((leg) => ({
    id: leg.id,
    assetId: leg.asset_id,
    accountId: leg.account_chain_id,
    accountName: accountNamesById.get(leg.account_chain_id) ?? leg.account_chain_id,
    quantity: leg.quantity,
    isFee: leg.is_fee,
  }));

const mapLedgerEvent = (
  event: ApiLedgerEvent,
  accountNamesById: Map<string, string>,
): EventCardData => ({
  id: event.id,
  timestamp: event.timestamp,
  place: event.origin.location.toLowerCase(),
  originId: event.origin.external_id,
  legs: mapLegs(event.legs, accountNamesById),
});

export const COLUMN_DEFINITIONS: Record<ColumnKey, ColumnDefinition> = {
  raw: {
    load: async () => {
      const [events, accountNamesById] = await Promise.all([
        getRawEvents(),
        getAccountNamesById(),
      ]);
      return events.map((event: ApiLedgerEvent) =>
        mapLedgerEvent(event, accountNamesById),
      );
    },
  },
  corrections: {
    load: async () => {
      const [events, accountNamesById] = await Promise.all([
        getSeedEvents(),
        getAccountNamesById(),
      ]);
      return events.map((event: ApiSeedEvent) => ({
        id: event.id,
        timestamp: event.timestamp,
        place: "",
        originId: "",
        legs: mapLegs(event.legs, accountNamesById),
      }));
    },
  },
  corrected: {
    load: async () => {
      const [events, accountNamesById] = await Promise.all([
        getCorrectedEvents(),
        getAccountNamesById(),
      ]);
      return events.map((event: ApiLedgerEvent) =>
        mapLedgerEvent(event, accountNamesById),
      );
    },
  },
} as const;
