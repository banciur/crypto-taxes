export type EventLeg = {
  id: string;
  assetId: string;
  accountId: string;
  accountName: string;
  quantity: string;
  isFee: boolean;
};

export type EventCardProps = {
  timestamp: string;
  place: string;
  originId: string;
  legs: EventLeg[];
};

export type EventCardData = EventCardProps & {
  id: string;
};
