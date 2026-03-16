import { doApiRequest, getFromApi } from "@/api/core";
import { orderByTimestamp } from "@/lib/sort";
import type {
  ReplacementCorrection,
  ReplacementCorrectionCreatePayload,
} from "@/types/events";

export const getReplacementCorrections = async (): Promise<
  ReplacementCorrection[]
> => {
  const events = await getFromApi<ReplacementCorrection[]>(
    "/replacement-corrections",
  );
  return orderByTimestamp(events);
};

export const deleteReplacementCorrection = async (
  correctionId: string,
): Promise<void> => {
  await doApiRequest(`/replacement-corrections/${correctionId}`, {
    method: "DELETE",
  });
};

export const createReplacementCorrection = async (
  payload: ReplacementCorrectionCreatePayload,
): Promise<ReplacementCorrection> =>
  (await doApiRequest<ReplacementCorrection>("/replacement-corrections", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: payload,
  })) as ReplacementCorrection;
