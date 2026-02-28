import { getFromApi, mutateApi } from "@/api/core";

type ApiEventOriginDto = {
  location: string;
  external_id: string;
};

export type ApiLedgerLeg = {
  id: string;
  asset_id: string;
  account_chain_id: string;
  quantity: string;
  is_fee: boolean;
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

export type ApiSpamCorrection = {
  id: string;
  eventOrigin: EventOrigin;
  timestamp: string;
};

type ApiSpamCorrectionDto = {
  id: string;
  event_origin: ApiEventOriginDto;
  timestamp: string;
};

export type ApiAccount = {
  account_chain_id: string;
  name: string;
  chain: string;
  address: string;
  skip_sync: boolean;
};

export type EventOrigin = {
  location: string;
  externalId: string;
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

const normalizeSpamCorrection = (
  event: ApiSpamCorrectionDto,
): ApiSpamCorrection => ({
  id: event.id,
  eventOrigin: normalizeEventOrigin(event.event_origin),
  timestamp: event.timestamp,
});

const orderEvents = <T extends { id: string; timestamp: string }>(
  events: T[],
) =>
  [...events].sort((a, b) => {
    const aTime = Date.parse(a.timestamp);
    const bTime = Date.parse(b.timestamp);
    if (aTime !== bTime) {
      return bTime - aTime;
    }
    return a.id.localeCompare(b.id);
  });

export const getRawEvents = async (): Promise<ApiLedgerEvent[]> => {
  const events = await getFromApi<ApiLedgerEventDto[]>("/raw-events");
  return orderEvents(events.map(normalizeLedgerEvent));
};

export const getCorrectedEvents = async (): Promise<ApiLedgerEvent[]> => {
  const events = await getFromApi<ApiLedgerEventDto[]>("/corrected-events");
  return orderEvents(events.map(normalizeLedgerEvent));
};

export const getSeedEvents = async (): Promise<ApiSeedEvent[]> => {
  const events = await getFromApi<ApiSeedEventDto[]>("/seed-events");
  return orderEvents(events.map(normalizeSeedEvent));
};

export const getSpamCorrections = async (): Promise<ApiSpamCorrection[]> => {
  const events = await getFromApi<ApiSpamCorrectionDto[]>("/spam-corrections");
  return orderEvents(events.map(normalizeSpamCorrection));
};

export const getAccounts = async (): Promise<ApiAccount[]> =>
  getFromApi<ApiAccount[]>("/accounts");

const buildSpamCorrectionPayload = (eventOrigin: EventOrigin) => ({
  event_origin: {
    location: eventOrigin.location,
    external_id: eventOrigin.externalId,
  },
});

export const createSpamCorrection = async (
  eventOrigin: EventOrigin,
): Promise<void> =>
  mutateApi(
    "/spam-corrections",
    "POST",
    buildSpamCorrectionPayload(eventOrigin),
  );

export const deleteSpamCorrection = async (
  eventOrigin: EventOrigin,
): Promise<void> =>
  mutateApi(
    "/spam-corrections",
    "DELETE",
    buildSpamCorrectionPayload(eventOrigin),
  );
