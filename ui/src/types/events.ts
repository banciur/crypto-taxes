/*
Current problems with types:
  - I think having extra EventLeg is mistake, resolving name could be done when rendering
  - Raw and Corrected events are different, but in reality they should have the same structure. Some problems in processing
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

export type EventCardDisplayData = {
  timestamp: string;
  eventOrigin: EventOrigin;
  legs: EventLeg[];
};

type LaneItemBase = {
  id: string;
  timestamp: string;
};

export type RawEventCardData = LaneItemBase &
  EventCardDisplayData & {
    kind: "raw-event";
  };

export type CorrectedEventCardData = LaneItemBase &
  EventCardDisplayData & {
    kind: "corrected-event";
  };

export type SeedCorrectionItemData = LaneItemBase & {
  kind: "seed-correction";
  legs: EventLeg[];
};

export type SpamCorrectionItemData = LaneItemBase & {
  kind: "spam-correction";
  eventOrigin: EventOrigin;
};

export type LaneItemData =
  | RawEventCardData
  | CorrectedEventCardData
  | SeedCorrectionItemData
  | SpamCorrectionItemData;
