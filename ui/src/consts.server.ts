import "server-only";

import { getAcquisitionDisposal } from "@/api/acquisitionDisposal";
import { getCorrections } from "@/api/corrections";
import { getCorrectedEvents, getRawEvents } from "@/api/events";
import type { AssetId, LaneItemData } from "@/types/events";
import type { ColumnKey } from "@/consts";
import { orderByTimestamp } from "@/lib/sort";

type ColumnDefinition = {
  load: (assetFilter: AssetId | null) => Promise<LaneItemData[]>;
};

export const COLUMN_DEFINITIONS: Record<ColumnKey, ColumnDefinition> = {
  raw: {
    load: async (assetFilter) => {
      const events = await getRawEvents(assetFilter);
      return events.map((event) => ({
        ...event,
        kind: "raw-event" as const,
      }));
    },
  },
  corrected: {
    load: async (assetFilter) => {
      const events = await getCorrectedEvents(assetFilter);
      return events.map((event) => ({
        ...event,
        kind: "corrected-event" as const,
      }));
    },
  },
  corrections: {
    load: async (assetFilter) => {
      const corrections = await getCorrections(assetFilter);
      return orderByTimestamp(
        corrections.map((correction) => ({
          ...correction,
          kind: "correction" as const,
        })),
      );
    },
  },
  acquisitionDisposal: {
    // Items already carry their "ACQUISITION" / "DISPOSAL" discriminant from the
    // API, so no re-tagging is needed unlike the event/correction lanes.
    // The asset filter deliberately does not reach this lane; `ASSET_FILTERED_COLUMNS` lists the ones it does.
    load: async () => getAcquisitionDisposal(),
  },
} as const;
