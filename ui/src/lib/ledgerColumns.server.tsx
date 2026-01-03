import "server-only";

import { type ReactNode } from "react";

import {
  getCorrectedLedgerEvents,
  getLedgerEvents,
  getSeedEvents,
  type CorrectedLedgerEventWithLegs,
  type LedgerEventWithLegs,
  type SeedEventWithLegs,
} from "@/db/client";
import { ColumnKey } from "@/consts";
import { EventCard } from "@/components/EventCard";

export type ColumnEventsMap = {
  raw: LedgerEventWithLegs;
  corrections: SeedEventWithLegs;
  corrected: CorrectedLedgerEventWithLegs;
};

type ColumnDefinition<K extends ColumnKey> = {
  key: K;
  load: () => Promise<ColumnEventsMap[K][]>;
  render: (events: ColumnEventsMap[K][]) => ReactNode;
};

const defineColumn = <K extends ColumnKey>(definition: ColumnDefinition<K>) =>
  definition;

export const COLUMN_DEFINITIONS = [
  defineColumn({
    key: "raw",
    load: getLedgerEvents,
    render: (events) =>
      events.map((event) => (
        <EventCard
          key={event.id}
          timestamp={event.timestamp}
          eventType={event.eventType}
          place={event.originLocation}
          legs={event.ledgerLegs}
        />
      )),
  }),
  defineColumn({
    key: "corrections",
    load: getSeedEvents,
    render: (events) =>
      events.map((event) => (
        <EventCard
          key={event.id}
          timestamp={event.timestamp}
          eventType="seed"
          place=""
          legs={event.seedEventLegs}
        />
      )),
  }),
  defineColumn({
    key: "corrected",
    load: getCorrectedLedgerEvents,
    render: (events) =>
      events.map((event) => (
        <EventCard
          key={event.id}
          timestamp={event.timestamp}
          eventType={event.eventType}
          place={event.originLocation}
          legs={event.correctedLedgerLegs}
        />
      )),
  }),
];
