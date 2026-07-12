// This file is completely vibed and I didn't read it.
"use client";

import { usePathname, useSearchParams } from "next/navigation";

import { ASSET_PARAM_NAME } from "@/consts";
import { resolveAssetFilter } from "@/lib/assetFilter";
import type { AssetId } from "@/types/events";

type UseAssetFilterResult = {
  assetFilter: AssetId | null;
  hrefForAssetFilter: (nextAssetFilter: AssetId | null) => string;
};

export const useAssetFilter = (): UseAssetFilterResult => {
  const searchParams = useSearchParams();
  const pathname = usePathname();

  const hrefForAssetFilter = (nextAssetFilter: AssetId | null) => {
    const nextParams = new URLSearchParams(searchParams.toString());
    if (nextAssetFilter === null) {
      nextParams.delete(ASSET_PARAM_NAME);
    } else {
      nextParams.set(ASSET_PARAM_NAME, nextAssetFilter);
    }

    const query = nextParams.toString();
    return query ? `${pathname}?${query}` : pathname;
  };

  return {
    assetFilter: resolveAssetFilter(searchParams.get(ASSET_PARAM_NAME)),
    hrefForAssetFilter,
  };
};
