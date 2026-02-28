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

export type EventOriginData = {
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
    eventOrigin: EventOriginData;
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
  eventOrigin: EventOriginData;
};

export type LaneItemData =
  | RawEventCardData
  | CorrectedEventCardData
  | SeedCorrectionItemData
  | SpamCorrectionItemData;
