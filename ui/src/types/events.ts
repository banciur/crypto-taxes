/*
Current problems with types:
  - I think having extra EventLeg is a mistake; resolving name could be done when rendering
 */

export type Account = {
  accountChainId: string;
  name: string;
  chain: string;
  address: string;
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

export type EventLeg = LedgerLeg & {
  accountName: string;
};

type ItemBase = {
  id: string;
  timestamp: string;
};

export type EventCardDisplayData = ItemBase & {
  eventOrigin: EventOrigin;
  legs: EventLeg[];
};

export type RawEventCardData = EventCardDisplayData & {
  kind: "raw-event";
};

export type CorrectedEventCardData = EventCardDisplayData & {
  kind: "corrected-event";
};

export type SeedCorrectionItemData = ItemBase & {
  kind: "seed-correction";
  legs: EventLeg[];
};

export type SpamCorrectionItemData = ItemBase & {
  kind: "spam-correction";
  eventOrigin: EventOrigin;
};

export type LaneItemData =
  | RawEventCardData
  | CorrectedEventCardData
  | SeedCorrectionItemData
  | SpamCorrectionItemData;
