export const COLUMN_METADATA = {
  raw: { label: "Raw events" },
  corrections: { label: "Corrections" },
  corrected: { label: "Corrected events" },
} as const;

export type ColumnKey = keyof typeof COLUMN_METADATA;

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

export const COLUMNS_PARAM_NAME = "columns";

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
