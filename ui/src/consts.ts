const mapping = {
  raw: "Raw events",
  corrections: "Corrections",
  corrected: "Corrected events",
} as const;

export type ColumnKey = keyof typeof mapping;

export const COLUMN_NAMES: ReadonlyMap<ColumnKey, string> = new Map(
  Object.entries(mapping) as Array<[ColumnKey, string]>,
);

export const AVAILABLE_COLUMNS: ReadonlySet<ColumnKey> = new Set(
  Object.keys(mapping) as ColumnKey[],
);

export const DEFAULT_COLUMN: ColumnKey = "corrected";

export const COLUMNS_PARAM_NAME = "columns";
