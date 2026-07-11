import { getFromApi, mutateApi } from "@/api/core";
import type { CreatePriceOverridePayload, PriceOverride } from "@/types/events";

export const getPriceOverrides = async (): Promise<PriceOverride[]> =>
  getFromApi<PriceOverride[]>("/price-overrides");

export const createPriceOverride = async (
  payload: CreatePriceOverridePayload,
): Promise<PriceOverride> =>
  (await mutateApi<PriceOverride>(
    "/price-overrides",
    "POST",
    payload,
  )) as PriceOverride;

export const deletePriceOverride = async (
  priceOverrideId: string,
): Promise<void> => mutateApi(`/price-overrides/${priceOverrideId}`, "DELETE");
