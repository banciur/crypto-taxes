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

export type SpamCorrection = {
  id: string;
  eventOrigin: EventOrigin;
  timestamp: string;
};

export type ReplacementCorrection = {
  id: string;
  timestamp: string;
  sources: EventOrigin[];
  legs: LedgerLeg[];
};

export type SeedEvent = {
  id: string;
  timestamp: string;
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

export type LedgerEvent = {
  id: string;
  timestamp: string;
  eventOrigin: EventOrigin;
  ingestion: string;
  legs: LedgerLeg[];
};

type ItemBase = {
  id: string;
  timestamp: string;
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

export type SpamCorrectionItemData = ItemBase & {
  kind: "spam-correction";
  eventOrigin: EventOrigin;
};

export type ReplacementCorrectionItemData = ItemBase & {
  kind: "replacement-correction";
  sources: EventOrigin[];
  legs: LedgerLeg[];
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
