export const COLUMN_METADATA = {
  raw: { label: "Raw events", order: 1 },
  corrections: { label: "Corrections", order: 2 },
  corrected: { label: "Corrected events", order: 3 },
} as const;

export type ColumnKey = keyof typeof COLUMN_METADATA;

const columnOrders = Object.values(COLUMN_METADATA).map(
  (column) => column.order,
);
if (new Set(columnOrders).size !== columnOrders.length) {
  throw new Error("COLUMN_METADATA order values must be unique.");
}

export const COLUMN_NAMES: ReadonlyMap<ColumnKey, string> = new Map(
  Object.entries(COLUMN_METADATA).map(([key, value]) => [
    key as ColumnKey,
    value.label,
  ]),
);

export const AVAILABLE_COLUMNS: ReadonlySet<ColumnKey> = new Set(
  Object.keys(COLUMN_METADATA) as ColumnKey[],
);

export const DEFAULT_COLUMN: ColumnKey = "corrected";
if (!Object.keys(COLUMN_METADATA).includes(DEFAULT_COLUMN)) {
  throw new Error("DEFAULT_COLUMN must exist in COLUMN_METADATA.");
}

export const COLUMNS_PARAM_NAME = "columns";

export const orderColumnKeys = (keys: Iterable<ColumnKey>): ColumnKey[] =>
  Array.from(keys).sort(
    (left, right) => COLUMN_METADATA[left].order - COLUMN_METADATA[right].order,
  );

export type ChainMetadata = {
  tracker: string;
};

export const CHAIN_METADATA = {
  optimism: {
    tracker: "https://optimistic.etherscan.io/",
  },
  base: {
    tracker: "https://basescan.org/",
  },
  arbitrum: {
    tracker: "https://arbiscan.io/",
  },
  ethereum: {
    tracker: "https://etherscan.io/",
  },
} as const satisfies Record<string, ChainMetadata>;

export type ChainKey = keyof typeof CHAIN_METADATA;
