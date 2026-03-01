export type EventOrigin = {
  location: string;
  externalId: string;
};

export type ApiLedgerLeg = {
  id: string;
  asset_id: string;
  account_chain_id: string;
  quantity: string;
  is_fee: boolean;
};
