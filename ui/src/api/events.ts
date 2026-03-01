import { getFromApi } from "@/api/core";
import type { ApiLedgerLeg, EventOrigin } from "@/api/types";
import { orderByTimestamp } from "@/lib/sort";

type ApiEventOriginDto = {
  location: string;
  external_id: string;
};

export type ApiLedgerEvent = {
  id: string;
  timestamp: string;
  eventOrigin: EventOrigin;
  ingestion: string;
  legs: ApiLedgerLeg[];
};

type ApiLedgerEventDto = {
  id: string;
  timestamp: string;
  event_origin: ApiEventOriginDto;
  ingestion: string;
  legs: ApiLedgerLeg[];
};

export type ApiSeedEvent = {
  id: string;
  timestamp: string;
  price_per_token: string;
  legs: ApiLedgerLeg[];
};

type ApiSeedEventDto = {
  id: string;
  timestamp: string;
  price_per_token: string;
  legs: ApiLedgerLeg[];
};

const normalizeEventOrigin = (eventOrigin: ApiEventOriginDto): EventOrigin => ({
  location: eventOrigin.location,
  externalId: eventOrigin.external_id,
});

const normalizeLedgerEvent = (event: ApiLedgerEventDto): ApiLedgerEvent => ({
  id: event.id,
  timestamp: event.timestamp,
  eventOrigin: normalizeEventOrigin(event.event_origin),
  ingestion: event.ingestion,
  legs: event.legs,
});

const normalizeSeedEvent = (event: ApiSeedEventDto): ApiSeedEvent => ({
  id: event.id,
  timestamp: event.timestamp,
  price_per_token: event.price_per_token,
  legs: event.legs,
});

export const getRawEvents = async (): Promise<ApiLedgerEvent[]> => {
  const events = await getFromApi<ApiLedgerEventDto[]>("/raw-events");
  return orderByTimestamp(events.map(normalizeLedgerEvent));
};

export const getCorrectedEvents = async (): Promise<ApiLedgerEvent[]> => {
  const events = await getFromApi<ApiLedgerEventDto[]>("/corrected-events");
  return orderByTimestamp(events.map(normalizeLedgerEvent));
};

export const getSeedEvents = async (): Promise<ApiSeedEvent[]> => {
  const events = await getFromApi<ApiSeedEventDto[]>("/seed-events");
  return orderByTimestamp(events.map(normalizeSeedEvent));
};
