export type EventLeg = {
  id: string;
  assetId: string;
  walletId: string;
  quantity: string;
  isFee: boolean;
};

export type EventCardProps = {
  timestamp: string;
  eventType: string;
  place: string;
  txHash: string;
  legs: EventLeg[];
};

export type EventCardData = EventCardProps & {
  id: string;
};
