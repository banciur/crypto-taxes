import "server-only";

import {
  getCorrectedEvents,
  getRawEvents,
  getSeedEvents,
  type LedgerEvent,
  type SeedEvent,
} from "@/api/events";
import {
  getSpamCorrections,
  type SpamCorrection,
} from "@/api/spamCorrections";
import type { LedgerLeg } from "@/api/types";
import type {
  CorrectedEventCardData,
  EventLeg,
  LaneItemData,
  RawEventCardData,
  SeedCorrectionItemData,
  SpamCorrectionItemData,
} from "@/types/events";
import type { ColumnKey } from "@/consts";
import { getAccountNamesById } from "@/lib/accounts";
import { orderByTimestamp } from "@/lib/sort";

type ColumnDefinition = {
  load: () => Promise<LaneItemData[]>;
};

const mapLegs = (
  legs: LedgerLeg[],
  accountNamesById: Map<string, string>,
): EventLeg[] =>
  legs.map((leg) => ({
    id: leg.id,
    assetId: leg.assetId,
    accountId: leg.accountChainId,
    accountName: accountNamesById.get(leg.accountChainId) ?? leg.accountChainId,
    quantity: leg.quantity,
    isFee: leg.isFee,
  }));

const mapRawLedgerEvent = (
  event: LedgerEvent,
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
  event: LedgerEvent,
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
  event: SeedEvent,
  accountNamesById: Map<string, string>,
): SeedCorrectionItemData => ({
  id: event.id,
  kind: "seed-correction",
  timestamp: event.timestamp,
  legs: mapLegs(event.legs, accountNamesById),
});

const mapSpamCorrectionItem = (
  event: SpamCorrection,
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

export const COLUMN_DEFINITIONS: Record<ColumnKey, ColumnDefinition> = {
  raw: {
    load: async () => {
      const [events, accountNamesById] = await Promise.all([
        getRawEvents(),
        getAccountNamesById(),
      ]);
      return events.map((event: LedgerEvent) =>
        mapRawLedgerEvent(event, accountNamesById),
      );
    },
  },
  corrections: {
    load: async () => {
      const [seedEvents, spamCorrections, accountNamesById] = await Promise.all(
        [getSeedEvents(), getSpamCorrections(), getAccountNamesById()],
      );
      return orderByTimestamp([
        ...seedEvents.map((event: SeedEvent) =>
          mapSeedCorrectionItem(event, accountNamesById),
        ),
        ...spamCorrections.map((event: SpamCorrection) =>
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
      return events.map((event: LedgerEvent) =>
        mapCorrectedLedgerEvent(event, accountNamesById),
      );
    },
  },
} as const;
