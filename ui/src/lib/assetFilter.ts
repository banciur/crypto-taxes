// This file is completely vibed and I didn't read it.
import type { AssetId } from "@/types/events";

export const resolveAssetFilter = (
  value: string | string[] | null | undefined,
): AssetId | null => {
  if (!value) {
    return null;
  }

  const normalized = (Array.isArray(value) ? (value[0] ?? "") : value).trim();

  return normalized.length > 0 ? normalized : null;
};
