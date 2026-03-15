import { getFromApi } from "@/api/core";
import { orderByTimestamp } from "@/lib/sort";
import type { ReplacementCorrection } from "@/types/events";

export const getReplacementCorrections = async (): Promise<
  ReplacementCorrection[]
> => {
  const events = await getFromApi<ReplacementCorrection[]>(
    "/replacement-corrections",
  );
  return orderByTimestamp(events);
};
