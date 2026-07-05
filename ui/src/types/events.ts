import type { ColumnKey } from "@/consts";

export type DecimalString = string;
export type AccountChainId = string;
export type AssetId = string;

export type Account = {
  accountChainId: AccountChainId;
  displayName: string;
  skipSync: boolean;
};

export type EventOrigin = {
  location: string;
  externalId: string;
};

export type LedgerLeg = {
  id: string;
  assetId: AssetId;
  accountChainId: AccountChainId;
  quantity: DecimalString;
  isFee: boolean;
};

export type LedgerCorrectionDraftLeg = Omit<LedgerLeg, "id">;

export type CreateLedgerCorrectionPayload = {
  timestamp: string;
  sources: EventOrigin[];
  legs: LedgerCorrectionDraftLeg[];
  note?: string;
};

type ItemBase = {
  id: string;
  timestamp: string;
};

export type LedgerCorrection = ItemBase & {
  sources: EventOrigin[];
  legs: LedgerLeg[];
  note?: string;
};

export type LedgerEvent = ItemBase & {
  eventOrigin: EventOrigin;
  ingestion: string;
  note?: string;
  legs: LedgerLeg[];
};

export type RawEventCardData = LedgerEvent & {
  kind: "raw-event";
};

export type CorrectedEventCardData = LedgerEvent & {
  kind: "corrected-event";
};

export type CorrectionItemData = LedgerCorrection & {
  kind: "correction";
};

type AcquisitionDisposalBase = ItemBase & {
  eventOrigin: EventOrigin;
  accountChainId: AccountChainId;
  assetId: AssetId;
  isFee: boolean;
};

export type AcquisitionItemData = AcquisitionDisposalBase & {
  kind: "ACQUISITION";
  quantityAcquired: DecimalString;
  costPerUnit: DecimalString;
};

export type DisposalItemData = AcquisitionDisposalBase & {
  kind: "DISPOSAL";
  acquisitionId: string;
  acquisitionTimestamp: string;
  acquisitionEventOrigin: EventOrigin;
  quantityUsed: DecimalString;
  proceedsTotal: DecimalString;
  costBasisTotal: DecimalString;
};

export type AcquisitionDisposalItemData =
  | AcquisitionItemData
  | DisposalItemData;

export type LaneItemData =
  | RawEventCardData
  | CorrectedEventCardData
  | CorrectionItemData
  | AcquisitionItemData
  | DisposalItemData;

export type EventsByTimestamp = Record<
  string,
  Partial<Record<ColumnKey, LaneItemData[]>>
>;
