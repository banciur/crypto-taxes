import "server-only";

import {
  getCorrectedEvents,
  getRawEvents,
  getSeedEvents,
  type ApiLedgerEvent,
  type ApiSeedEvent,
} from "@/api/events";
import { getAccounts, type ApiAccount } from "@/api/accounts";
import {
  getSpamCorrections,
  type ApiSpamCorrection,
} from "@/api/spamCorrections";
import type { ApiLedgerLeg } from "@/api/types";
import type {
  CorrectedEventCardData,
  EventLeg,
  LaneItemData,
  RawEventCardData,
  SeedCorrectionItemData,
  SpamCorrectionItemData,
} from "@/types/events";
import type { ColumnKey } from "@/consts";

type ColumnDefinition = {
  load: () => Promise<LaneItemData[]>;
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
    accountName:
      accountNamesById.get(leg.account_chain_id) ?? leg.account_chain_id,
    quantity: leg.quantity,
    isFee: leg.is_fee,
  }));

const mapRawLedgerEvent = (
  event: ApiLedgerEvent,
  accountNamesById: Map<string, string>,
): RawEventCardData => ({
  id: event.id,
  kind: "raw-event",
  timestamp: event.timestamp,
  place: event.eventOrigin.location.toLowerCase(),
  originId: event.eventOrigin.externalId,
  legs: mapLegs(event.legs, accountNamesById),
  eventOrigin: {
    location: event.eventOrigin.location,
    externalId: event.eventOrigin.externalId,
  },
});

const mapCorrectedLedgerEvent = (
  event: ApiLedgerEvent,
  accountNamesById: Map<string, string>,
): CorrectedEventCardData => ({
  id: event.id,
  kind: "corrected-event",
  timestamp: event.timestamp,
  place: event.eventOrigin.location.toLowerCase(),
  originId: event.eventOrigin.externalId,
  legs: mapLegs(event.legs, accountNamesById),
});

const mapSeedCorrectionItem = (
  event: ApiSeedEvent,
  accountNamesById: Map<string, string>,
): SeedCorrectionItemData => ({
  id: event.id,
  kind: "seed-correction",
  timestamp: event.timestamp,
  legs: mapLegs(event.legs, accountNamesById),
});

const mapSpamCorrectionItem = (
  event: ApiSpamCorrection,
): SpamCorrectionItemData => ({
  id: event.id,
  kind: "spam-correction",
  timestamp: event.timestamp,
  place: event.eventOrigin.location.toLowerCase(),
  eventOrigin: {
    location: event.eventOrigin.location,
    externalId: event.eventOrigin.externalId,
  },
});

const orderLaneItems = <T extends { id: string; timestamp: string }>(
  items: T[],
): T[] =>
  [...items].sort((a, b) => {
    const aTime = Date.parse(a.timestamp);
    const bTime = Date.parse(b.timestamp);
    if (aTime !== bTime) {
      return bTime - aTime;
    }
    return a.id.localeCompare(b.id);
  });

export const COLUMN_DEFINITIONS: Record<ColumnKey, ColumnDefinition> = {
  raw: {
    load: async () => {
      const [events, accountNamesById] = await Promise.all([
        getRawEvents(),
        getAccountNamesById(),
      ]);
      return events.map((event: ApiLedgerEvent) =>
        mapRawLedgerEvent(event, accountNamesById),
      );
    },
  },
  corrections: {
    load: async () => {
      const [seedEvents, spamCorrections, accountNamesById] = await Promise.all(
        [getSeedEvents(), getSpamCorrections(), getAccountNamesById()],
      );
      return orderLaneItems([
        ...seedEvents.map((event: ApiSeedEvent) =>
          mapSeedCorrectionItem(event, accountNamesById),
        ),
        ...spamCorrections.map((event: ApiSpamCorrection) =>
          mapSpamCorrectionItem(event),
        ),
      ]);
    },
  },
  corrected: {
    load: async () => {
      const [events, accountNamesById] = await Promise.all([
        getCorrectedEvents(),
        getAccountNamesById(),
      ]);
      return events.map((event: ApiLedgerEvent) =>
        mapCorrectedLedgerEvent(event, accountNamesById),
      );
    },
  },
} as const;
