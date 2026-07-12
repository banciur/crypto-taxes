import { getFromApi } from "@/api/core";
import { orderByTimestamp } from "@/lib/sort";
import type { AssetId, LedgerEvent } from "@/types/events";

export const getRawEvents = async (
  assetFilter: AssetId | null,
): Promise<LedgerEvent[]> => {
  const events = await getFromApi<LedgerEvent[]>("/raw-events", {
    asset: assetFilter ?? undefined,
  });
  return orderByTimestamp(events);
};

export const getCorrectedEvents = async (
  assetFilter: AssetId | null,
): Promise<LedgerEvent[]> => {
  const events = await getFromApi<LedgerEvent[]>("/corrected-events", {
    asset: assetFilter ?? undefined,
  });
  return orderByTimestamp(events);
};
