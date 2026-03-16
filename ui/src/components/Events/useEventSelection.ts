"use client";

import { useCallback, useMemo, useState } from "react";

import { eventOriginKey } from "@/lib/eventOrigin";
import type { EventOrigin, EventsByTimestamp } from "@/types/events";
import { collectSelectableEventOriginKeys } from "./selectableEvents";

type UseEventSelectionResult = {
  selectedEventOriginKeys: ReadonlySet<string>;
  toggleEventSelection: (eventOrigin: EventOrigin) => void;
  clearEventSelection: () => void;
};

export const useEventSelection = (
  eventsByTimestamp: EventsByTimestamp,
): UseEventSelectionResult => {
  const [selectedEventOriginKeys, setSelectedEventOriginKeys] = useState<
    Set<string>
  >(() => new Set());

  const selectableEventOriginKeys = useMemo(
    () => collectSelectableEventOriginKeys(eventsByTimestamp),
    [eventsByTimestamp],
  );

  const effectiveSelectedEventOriginKeys = useMemo(
    () =>
      Array.from(selectedEventOriginKeys).filter((originKey) =>
        selectableEventOriginKeys.has(originKey),
      ),
    [selectableEventOriginKeys, selectedEventOriginKeys],
  );

  const effectiveSelectedEventOriginKeySet = useMemo(
    () => new Set(effectiveSelectedEventOriginKeys),
    [effectiveSelectedEventOriginKeys],
  );

  const toggleEventSelection = useCallback(
    (eventOrigin: EventOrigin) => {
      const originKey = eventOriginKey(eventOrigin);
      setSelectedEventOriginKeys((current) => {
        const next = new Set(
          Array.from(current).filter((selectedOriginKey) =>
            selectableEventOriginKeys.has(selectedOriginKey),
          ),
        );

        if (!selectableEventOriginKeys.has(originKey)) {
          return next;
        }

        if (next.has(originKey)) {
          next.delete(originKey);
        } else {
          next.add(originKey);
        }
        return next;
      });
    },
    [selectableEventOriginKeys],
  );

  const clearEventSelection = useCallback(() => {
    setSelectedEventOriginKeys(new Set());
  }, []);

  return {
    selectedEventOriginKeys: effectiveSelectedEventOriginKeySet,
    toggleEventSelection,
    clearEventSelection,
  };
};
