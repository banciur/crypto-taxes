import { getFromApi } from "@/api/core";
import type { LedgerLeg } from "@/api/types";
import { orderByTimestamp } from "@/lib/sort";
import type { EventOrigin } from "@/types/events";

export type LedgerEvent = {
  id: string;
  timestamp: string;
  eventOrigin: EventOrigin;
  ingestion: string;
  legs: LedgerLeg[];
};

export type SeedEvent = {
  id: string;
  timestamp: string;
  pricePerToken: string;
  legs: LedgerLeg[];
};

export const getRawEvents = async (): Promise<LedgerEvent[]> => {
  const events = await getFromApi<LedgerEvent[]>("/raw-events");
  return orderByTimestamp(events);
};

export const getCorrectedEvents = async (): Promise<LedgerEvent[]> => {
  const events = await getFromApi<LedgerEvent[]>("/corrected-events");
  return orderByTimestamp(events);
};

export const getSeedEvents = async (): Promise<SeedEvent[]> => {
  const events = await getFromApi<SeedEvent[]>("/seed-events");
  return orderByTimestamp(events);
};
