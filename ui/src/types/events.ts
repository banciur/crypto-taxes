/*
Current problems with types:
  - ledger legs there are ones from the api and ones with translated wallet name
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

type LegBase = {
  id: string;
  assetId: string;
  quantity: string;
  isFee: boolean;
};

export type LedgerLeg = LegBase & {
  accountChainId: string;
};

export type LedgerEvent = {
  id: string;
  timestamp: string;
  eventOrigin: EventOrigin;
  ingestion: string;
  legs: LedgerLeg[];
};

export type EventLeg = LegBase & {
  accountId: string;
  accountName: string;
};

export type EventCardDisplayData = {
  timestamp: string;
  place: string;
  originId: string;
  legs: EventLeg[];
};

type LaneItemBase = {
  id: string;
  timestamp: string;
};

export type RawEventCardData = LaneItemBase &
  EventCardDisplayData & {
    kind: "raw-event";
    eventOrigin: EventOrigin;
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
  place: string;
  eventOrigin: EventOrigin;
};

export type LaneItemData =
  | RawEventCardData
  | CorrectedEventCardData
  | SeedCorrectionItemData
  | SpamCorrectionItemData;
