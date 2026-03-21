import "server-only";

import { getCorrections } from "@/api/corrections";
import { getCorrectedEvents, getRawEvents } from "@/api/events";
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
        ...event,
        kind: "raw-event" as const,
      }));
    },
  },
  corrected: {
    load: async () => {
      const events = await getCorrectedEvents();
      return events.map((event) => ({
        ...event,
        kind: "corrected-event" as const,
      }));
    },
  },
  corrections: {
    load: async () => {
      const corrections = await getCorrections();
      return orderByTimestamp(
        corrections.map((correction) => ({
          ...correction,
          kind: "correction" as const,
        })),
      );
    },
  },
} as const;
