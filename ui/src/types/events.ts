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

export type PriceOverride = {
  id: string;
  eventOrigin: EventOrigin;
  assetId: AssetId;
  rateEur: DecimalString;
  note?: string;
};

export type CreatePriceOverridePayload = Omit<PriceOverride, "id">;

/**
 * The corrected-event asset a price override is being authored against.
 *
 * An override is identified by `(eventOrigin, assetId)` and applies to the asset across the whole
 * event. `legQuantity` is not part of that identity: it is the quantity of the leg the editor was
 * opened from, and the editor only uses it to convert between the rate and total-value inputs.
 */
export type PriceOverrideEditorContext = {
  eventOrigin: EventOrigin;
  assetId: AssetId;
  legQuantity: DecimalString;
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
