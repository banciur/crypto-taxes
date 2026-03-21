import { getFromApi, mutateApi } from "@/api/core";
import { orderByTimestamp } from "@/lib/sort";
import type {
  CreateLedgerCorrectionPayload,
  LedgerCorrection,
} from "@/types/events";

export const getCorrections = async (): Promise<LedgerCorrection[]> => {
  const corrections = await getFromApi<LedgerCorrection[]>("/corrections");
  return orderByTimestamp(corrections);
};

export const createCorrection = async (
  payload: CreateLedgerCorrectionPayload,
): Promise<LedgerCorrection> =>
  (await mutateApi<LedgerCorrection>(
    "/corrections",
    "POST",
    payload,
  )) as LedgerCorrection;

export const deleteCorrection = async (correctionId: string): Promise<void> =>
  mutateApi(`/corrections/${correctionId}`, "DELETE");
