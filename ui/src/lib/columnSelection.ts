import { AVAILABLE_COLUMNS, ColumnKey, DEFAULT_COLUMN } from "@/consts";

const parseColumnsParam = (
  value: string | string[] | null | undefined,
): Set<string> => {
  if (!value) {
    return new Set();
  }

  const normalized = Array.isArray(value) ? value.join(",") : value;

  return new Set(
    normalized
      .split(",")
      .map((entry) => entry.trim())
      .filter((entry) => entry.length > 0),
  );
};

export const resolveSelectedColumns = (
  value: string | string[] | null | undefined,
): Set<ColumnKey> => {
  const rawColumns = parseColumnsParam(value);
  const selected = AVAILABLE_COLUMNS.intersection(rawColumns);

  if (selected.size === 0) {
    return new Set([DEFAULT_COLUMN]);
  }

  return selected;
};
