"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
  useCallback,
} from "react";

import { eventOriginKey } from "@/lib/eventOrigin";
import type { EventOrigin } from "@/types/events";

type SourceHighlight = {
  accentColor: string;
  surfaceColor: string;
};

type SourceHighlightLookup = Readonly<Partial<Record<string, SourceHighlight>>>;

const GOLDEN_ANGLE_DEGREES = 137.508;

const createSourceHighlight = (index: number): SourceHighlight => {
  const hue = (index * GOLDEN_ANGLE_DEGREES) % 360;
  const roundedHue = hue.toFixed(1);

  return {
    accentColor: `hsl(${roundedHue}deg 62% 45%)`,
    surfaceColor: `hsl(${roundedHue}deg 85% 93%)`,
  };
};

const buildSourceHighlightLookup = (
  sources: EventOrigin[],
): SourceHighlightLookup =>
  Object.fromEntries(
    sources.map((source, index) => [
      eventOriginKey(source),
      createSourceHighlight(index),
    ]),
  );

type CorrectionHighlightContextType = {
  setHighlightedSources: (sources: EventOrigin[]) => void;
  clearHighlightedSources: () => void;
  getSourceHighlight: (eventOrigin: EventOrigin) => SourceHighlight | undefined;
};

const CorrectionHighlightContext = createContext<
  CorrectionHighlightContextType | undefined
>(undefined);

export function CorrectionHighlightProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [sourceHighlights, setSourceHighlights] =
    useState<SourceHighlightLookup>({});

  const setHighlightedSources = (sources: EventOrigin[]) =>
    setSourceHighlights(buildSourceHighlightLookup(sources));

  const clearHighlightedSources = () => {
    setSourceHighlights({});
  };

  const getSourceHighlight = useCallback(
    (eventOrigin: EventOrigin) => sourceHighlights[eventOriginKey(eventOrigin)],
    [sourceHighlights],
  );

  const value = useMemo(
    () => ({
      setHighlightedSources,
      clearHighlightedSources,
      getSourceHighlight,
    }),
    [getSourceHighlight],
  );

  return (
    <CorrectionHighlightContext.Provider value={value}>
      {children}
    </CorrectionHighlightContext.Provider>
  );
}

export function useCorrectionHighlight(): CorrectionHighlightContextType {
  const context = useContext(CorrectionHighlightContext);
  if (!context) {
    throw new Error(
      "useCorrectionHighlight must be used within CorrectionHighlightProvider",
    );
  }

  return context;
}
