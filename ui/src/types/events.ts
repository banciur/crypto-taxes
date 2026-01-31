import type { ColumnKey } from "@/consts";

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

export type ColumnEvents = {
  key: ColumnKey;
  events: EventCardData[];
};

export type LedgerDateSection = {
  key: string;
  count: number;
  columns: ColumnEvents[];
};
