import "server-only";

import { getCorrectedEvents, getRawEvents, getSeedEvents } from "@/api/events";
import { getReplacementCorrections } from "@/api/replacementCorrections";
import { getSpamCorrections } from "@/api/spamCorrections";
import type { LaneItemData } from "@/types/events";
import type { ColumnKey } from "@/consts";
import { orderByTimestamp } from "@/lib/sort";

type ColumnDefinition = {
  load: () => Promise<LaneItemData[]>;
};

export const COLUMN_DEFINITIONS: Record<ColumnKey, ColumnDefinition> = {
  raw: {
    load: async () => {
      const events = await getRawEvents();
      return events.map((event) => ({
        id: event.id,
        kind: "raw-event" as const,
        timestamp: event.timestamp,
        legs: event.legs,
        eventOrigin: event.eventOrigin,
      }));
    },
  },
  corrections: {
    load: async () => {
      const [seedEvents, spamCorrections, replacementCorrections] =
        await Promise.all([
        getSeedEvents(),
        getSpamCorrections(),
        getReplacementCorrections(),
      ]);
      return orderByTimestamp([
        ...seedEvents.map((event) => ({
          id: event.id,
          kind: "seed-correction" as const,
          timestamp: event.timestamp,
          legs: event.legs,
        })),
        ...spamCorrections.map((event) => ({
          ...event,
          kind: "spam-correction" as const,
        })),
        ...replacementCorrections.map((event) => ({
          ...event,
          kind: "replacement-correction" as const,
        })),
      ]);
    },
  },
  corrected: {
    load: async () => {
      const events = await getCorrectedEvents();
      return events.map((event) => ({
        id: event.id,
        kind: "corrected-event" as const,
        timestamp: event.timestamp,
        eventOrigin: event.eventOrigin,
        legs: event.legs,
      }));
    },
  },
} as const;
