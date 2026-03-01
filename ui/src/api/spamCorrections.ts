import { orderByTimestampDesc } from "@/api/helpers";
import { getFromApi, mutateApi } from "@/api/core";
import type { EventOrigin } from "@/api/types";

type ApiEventOriginDto = {
  location: string;
  external_id: string;
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

const normalizeEventOrigin = (eventOrigin: ApiEventOriginDto): EventOrigin => ({
  location: eventOrigin.location,
  externalId: eventOrigin.external_id,
});

const normalizeSpamCorrection = (
  event: ApiSpamCorrectionDto,
): ApiSpamCorrection => ({
  id: event.id,
  eventOrigin: normalizeEventOrigin(event.event_origin),
  timestamp: event.timestamp,
});

const buildSpamCorrectionPayload = (eventOrigin: EventOrigin) => ({
  event_origin: {
    location: eventOrigin.location,
    external_id: eventOrigin.externalId,
  },
});

export const getSpamCorrections = async (): Promise<ApiSpamCorrection[]> => {
  const events = await getFromApi<ApiSpamCorrectionDto[]>("/spam-corrections");
  return orderByTimestampDesc(events.map(normalizeSpamCorrection));
};

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
