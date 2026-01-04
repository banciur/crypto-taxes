import "server-only";

import {
  getCorrectedLedgerEvents,
  getLedgerEvents,
  getSeedEvents,
  type CorrectedLedgerEventWithLegs,
  type LedgerEventWithLegs,
  type SeedEventWithLegs,
} from "@/db/client";
import { ColumnKey } from "@/consts";
import { EventCardProps } from "@/components/EventCard";

type ColumnDefinition = {
  load: () => Promise<any[]>; // eslint-disable-line @typescript-eslint/no-explicit-any
  transform: (obj: any) => EventCardProps; // eslint-disable-line @typescript-eslint/no-explicit-any
};

export const COLUMN_DEFINITIONS: Record<ColumnKey, ColumnDefinition> = {
  raw: {
    load: getLedgerEvents,
    transform: (obj: LedgerEventWithLegs) => ({
      timestamp: obj.timestamp,
      eventType: obj.eventType,
      place: obj.originLocation,
      legs: obj.ledgerLegs,
    }),
  },
  corrections: {
    load: getSeedEvents,
    transform: (obj: SeedEventWithLegs) => ({
      timestamp: obj.timestamp,
      eventType: "seed",
      place: "",
      legs: obj.seedEventLegs,
    }),
  },
  corrected: {
    load: getCorrectedLedgerEvents,
    transform: (obj: CorrectedLedgerEventWithLegs) => ({
      timestamp: obj.timestamp,
      eventType: obj.eventType,
      place: obj.originLocation,
      legs: obj.correctedLedgerLegs,
    }),
  },
} as const;
