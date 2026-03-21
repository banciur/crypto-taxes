import { getFromApi } from "@/api/core";
import { orderByTimestamp } from "@/lib/sort";
import type { LedgerEvent } from "@/types/events";

export const getRawEvents = async (): Promise<LedgerEvent[]> => {
  const events = await getFromApi<LedgerEvent[]>("/raw-events");
  return orderByTimestamp(events);
};

export const getCorrectedEvents = async (): Promise<LedgerEvent[]> => {
  const events = await getFromApi<LedgerEvent[]>("/corrected-events");
  return orderByTimestamp(events);
};
