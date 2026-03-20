import { getFromApi, mutateApi } from "@/api/core";
import { orderByTimestamp } from "@/lib/sort";
import type {
  CreateReplacementCorrectionPayload,
  ReplacementCorrection,
} from "@/types/events";

export const getReplacementCorrections = async (): Promise<
  ReplacementCorrection[]
> => {
  const events = await getFromApi<ReplacementCorrection[]>(
    "/replacement-corrections",
  );
  return orderByTimestamp(events);
};

export const createReplacementCorrection = async (
  payload: CreateReplacementCorrectionPayload,
): Promise<ReplacementCorrection> =>
  (await mutateApi<ReplacementCorrection>(
    "/replacement-corrections",
    "POST",
    payload,
  )) as ReplacementCorrection;

export const deleteReplacementCorrection = async (
  correctionId: string,
): Promise<void> =>
  mutateApi(`/replacement-corrections/${correctionId}`, "DELETE");
