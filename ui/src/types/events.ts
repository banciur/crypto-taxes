export type EventLeg = {
  id: string;
  assetId: string;
  accountId: string;
  accountName: string;
  quantity: string;
  isFee: boolean;
};

export type EventCardDisplayData = {
  timestamp: string;
  place: string;
  originId: string;
  legs: EventLeg[];
};

export type EventOrigin = {
  location: string;
  externalId: string;
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
