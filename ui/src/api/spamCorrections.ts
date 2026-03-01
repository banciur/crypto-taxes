import { getFromApi, mutateApi } from "@/api/core";
import { orderByTimestamp } from "@/lib/sort";
import type { EventOrigin, SpamCorrection } from "@/types/events";

const buildSpamCorrectionPayload = (eventOrigin: EventOrigin) => ({
  eventOrigin,
});

export const getSpamCorrections = async (): Promise<SpamCorrection[]> => {
  const events = await getFromApi<SpamCorrection[]>("/spam-corrections");
  return orderByTimestamp(events);
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
