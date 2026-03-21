import type { ColumnKey } from "@/consts";

export type DecimalString = string;

export type Account = {
  accountChainId: string;
  displayName: string;
  skipSync: boolean;
};

export type EventOrigin = {
  location: string;
  externalId: string;
};

type ItemBase = {
  id: string;
  timestamp: string;
};

export type LedgerCorrection = ItemBase & {
  sources: EventOrigin[];
  legs: LedgerLeg[];
  pricePerToken: DecimalString | null;
  note: string;
};

export type LedgerLeg = {
  id: string;
  assetId: string;
  accountChainId: string;
  quantity: DecimalString;
  isFee: boolean;
};

export type LedgerEvent = ItemBase & {
  eventOrigin: EventOrigin;
  ingestion: string;
  legs: LedgerLeg[];
};

export type RawEventCardData = LedgerEvent & {
  kind: "raw-event";
};

export type CorrectedEventCardData = LedgerEvent & {
  kind: "corrected-event";
};

export type LedgerCorrectionDraftLeg = Omit<LedgerLeg, "id">;

export type CreateLedgerCorrectionPayload = {
  timestamp?: string;
  sources: EventOrigin[];
  legs: LedgerCorrectionDraftLeg[];
  pricePerToken?: DecimalString | null;
  note: string;
};

export type CorrectionItemData = LedgerCorrection & {
  kind: "correction";
};

export type LaneItemData =
  | RawEventCardData
  | CorrectedEventCardData
  | CorrectionItemData;

export type EventsByTimestamp = Record<
  string,
  Partial<Record<ColumnKey, LaneItemData[]>>
>;
