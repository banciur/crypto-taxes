import { getFromApi } from "@/api/core";
import { orderByTimestamp } from "@/lib/sort";
import type { AcquisitionDisposalItemData } from "@/types/events";

export const getAcquisitionDisposal = async (): Promise<
  AcquisitionDisposalItemData[]
> => {
  const items = await getFromApi<AcquisitionDisposalItemData[]>(
    "/acquisition-disposal",
  );
  return orderByTimestamp(items);
};
