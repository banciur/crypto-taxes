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
