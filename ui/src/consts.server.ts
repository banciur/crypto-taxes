import "server-only";

import {
  getCorrectedEvents,
  getRawEvents,
  getSeedEvents,
  type ApiLedgerEvent,
  type ApiLedgerLeg,
  type ApiSeedEvent,
} from "@/api/events";
import type { ColumnKey } from "@/consts";
import type { EventCardData, EventLeg } from "@/types/events";

type ColumnDefinition = {
  load: () => Promise<any[]>; // eslint-disable-line @typescript-eslint/no-explicit-any
  transform: (obj: any) => EventCardData; // eslint-disable-line @typescript-eslint/no-explicit-any
};

const mapLegs = (legs: ApiLedgerLeg[]): EventLeg[] =>
  legs.map((leg) => ({
    id: leg.id,
    assetId: leg.asset_id,
    walletId: leg.wallet_id,
    quantity: leg.quantity,
    isFee: leg.is_fee,
  }));

const mapLedgerEvent = (event: ApiLedgerEvent): EventCardData => ({
  id: event.id,
  timestamp: event.timestamp,
  place: event.origin.location.toLowerCase(),
  originId: event.origin.external_id,
  legs: mapLegs(event.legs),
});

export const COLUMN_DEFINITIONS: Record<ColumnKey, ColumnDefinition> = {
  raw: {
    load: getRawEvents,
    transform: (event: ApiLedgerEvent) => mapLedgerEvent(event),
  },
  corrections: {
    load: getSeedEvents,
    transform: (event: ApiSeedEvent) => ({
      id: event.id,
      timestamp: event.timestamp,
      place: "",
      originId: "",
      legs: mapLegs(event.legs),
    }),
  },
  corrected: {
    load: getCorrectedEvents,
    transform: (event: ApiLedgerEvent) => mapLedgerEvent(event),
  },
} as const;
