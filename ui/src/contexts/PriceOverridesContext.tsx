"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";

import { eventOriginKey } from "@/lib/eventOrigin";
import type { AssetId, EventOrigin, PriceOverride } from "@/types/events";

type PriceOverrideCatalog = {
  findPriceOverride: (
    eventOrigin: EventOrigin,
    assetId: AssetId,
  ) => PriceOverride | undefined;
};

const PriceOverridesContext = createContext<PriceOverrideCatalog | undefined>(
  undefined,
);

const priceOverrideKey = (eventOrigin: EventOrigin, assetId: AssetId) =>
  `${eventOriginKey(eventOrigin)}|${assetId}`;

export function PriceOverridesProvider({
  priceOverrides,
  children,
}: {
  priceOverrides: PriceOverride[];
  children: ReactNode;
}) {
  const value = useMemo<PriceOverrideCatalog>(() => {
    // An override prices one asset of one corrected event, which the API enforces as unique.
    const overridesByEventAsset = new Map(
      priceOverrides.map((priceOverride) => [
        priceOverrideKey(priceOverride.eventOrigin, priceOverride.assetId),
        priceOverride,
      ]),
    );

    return {
      findPriceOverride: (eventOrigin, assetId) =>
        overridesByEventAsset.get(priceOverrideKey(eventOrigin, assetId)),
    };
  }, [priceOverrides]);

  return (
    <PriceOverridesContext.Provider value={value}>
      {children}
    </PriceOverridesContext.Provider>
  );
}

export function usePriceOverrides(): PriceOverrideCatalog {
  const context = useContext(PriceOverridesContext);

  if (!context) {
    throw new Error(
      "usePriceOverrides must be used within PriceOverridesProvider",
    );
  }

  return context;
}
