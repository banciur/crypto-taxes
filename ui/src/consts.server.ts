import "server-only";

import { getCorrectedEvents, getRawEvents, getSeedEvents } from "@/api/events";
import { getSpamCorrections } from "@/api/spamCorrections";
import type {
  CorrectedEventCardData,
  EventLeg,
  LedgerEvent,
  LedgerLeg,
  LaneItemData,
  RawEventCardData,
  SeedEvent,
  SeedCorrectionItemData,
  SpamCorrection,
  SpamCorrectionItemData,
} from "@/types/events";
import type { ColumnKey } from "@/consts";
import { getAccountName } from "@/lib/accounts";
import { orderByTimestamp } from "@/lib/sort";

type ColumnDefinition = {
  load: () => Promise<LaneItemData[]>;
};

const mapLegs = (legs: LedgerLeg[]): EventLeg[] =>
  legs.map((leg) => ({
    id: leg.id,
    assetId: leg.assetId,
    accountId: leg.accountChainId,
    accountName: getAccountName(leg.accountChainId),
    quantity: leg.quantity,
    isFee: leg.isFee,
  }));

const mapRawLedgerEvent = (event: LedgerEvent): RawEventCardData => ({
  id: event.id,
  kind: "raw-event",
  timestamp: event.timestamp,
  place: event.eventOrigin.location.toLowerCase(),
  originId: event.eventOrigin.externalId,
  legs: mapLegs(event.legs),
  eventOrigin: {
    location: event.eventOrigin.location,
    externalId: event.eventOrigin.externalId,
  },
});

const mapCorrectedLedgerEvent = (
  event: LedgerEvent,
): CorrectedEventCardData => ({
  id: event.id,
  kind: "corrected-event",
  timestamp: event.timestamp,
  place: event.eventOrigin.location.toLowerCase(),
  originId: event.eventOrigin.externalId,
  legs: mapLegs(event.legs),
});

const mapSeedCorrectionItem = (event: SeedEvent): SeedCorrectionItemData => ({
  id: event.id,
  kind: "seed-correction",
  timestamp: event.timestamp,
  legs: mapLegs(event.legs),
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
      const events = await getRawEvents();
      return events.map((event: LedgerEvent) => mapRawLedgerEvent(event));
    },
  },
  corrections: {
    load: async () => {
      const [seedEvents, spamCorrections] = await Promise.all([
        getSeedEvents(),
        getSpamCorrections(),
      ]);
      return orderByTimestamp([
        ...seedEvents.map((event: SeedEvent) => mapSeedCorrectionItem(event)),
        ...spamCorrections.map((event: SpamCorrection) =>
          mapSpamCorrectionItem(event),
        ),
      ]);
    },
  },
  corrected: {
    load: async () => {
      const events = await getCorrectedEvents();
      return events.map((event: LedgerEvent) => mapCorrectedLedgerEvent(event));
    },
  },
} as const;
