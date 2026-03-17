import type { ColumnKey } from "@/consts";

export type Account = {
  accountChainId: string;
  name: string;
  location: string;
  address: string | null;
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

export type SpamCorrection = ItemBase & {
  eventOrigin: EventOrigin;
};

export type ReplacementCorrection = ItemBase & {
  sources: EventOrigin[];
  legs: LedgerLeg[];
};

export type ReplacementCorrectionDraftLeg = Omit<LedgerLeg, "id">;

export type CreateReplacementCorrectionPayload = {
  timestamp: string;
  sources: EventOrigin[];
  legs: ReplacementCorrectionDraftLeg[];
};

export type SeedEvent = ItemBase & {
  pricePerToken: string;
  legs: LedgerLeg[];
};

export type LedgerLeg = {
  id: string;
  assetId: string;
  accountChainId: string;
  quantity: string;
  isFee: boolean;
};

export type LedgerEvent = ItemBase & {
  eventOrigin: EventOrigin;
  ingestion: string;
  legs: LedgerLeg[];
};

export type EventCardDisplayData = ItemBase & {
  eventOrigin: EventOrigin;
  legs: LedgerLeg[];
};

export type RawEventCardData = EventCardDisplayData & {
  kind: "raw-event";
};

export type CorrectedEventCardData = EventCardDisplayData & {
  kind: "corrected-event";
};

export type SeedCorrectionItemData = ItemBase & {
  kind: "seed-correction";
  legs: LedgerLeg[];
};

export type SpamCorrectionItemData = SpamCorrection & {
  kind: "spam-correction";
};

export type ReplacementCorrectionItemData = ReplacementCorrection & {
  kind: "replacement-correction";
};

export type LaneItemData =
  | RawEventCardData
  | CorrectedEventCardData
  | SeedCorrectionItemData
  | SpamCorrectionItemData
  | ReplacementCorrectionItemData;

export type EventsByTimestamp = Record<
  string,
  Partial<Record<ColumnKey, LaneItemData[]>>
>;
