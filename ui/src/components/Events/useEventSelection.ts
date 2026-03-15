"use client";

import { useCallback, useMemo, useState } from "react";

import { eventOriginKey } from "@/lib/eventOrigin";
import type { EventOrigin, EventsByTimestamp } from "@/types/events";
import { collectSelectableEvents } from "./selectableEvents";

type UseEventSelectionResult = {
  selectedEventOrigins: readonly EventOrigin[];
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

  const selectableEvents = useMemo(
    () => collectSelectableEvents(eventsByTimestamp),
    [eventsByTimestamp],
  );

  const { effectiveSelectedEventOriginKeys, selectedEventOrigins } =
    useMemo(() => {
      const effectiveSelectedEventOriginKeys = new Set(
        Array.from(selectedEventOriginKeys).filter((originKey) =>
          selectableEvents.has(originKey),
        ),
      );

      const selectedEventOrigins = Array.from(effectiveSelectedEventOriginKeys)
        .map((originKey) => selectableEvents.get(originKey))
        .filter(
          (eventOrigin): eventOrigin is EventOrigin =>
            eventOrigin !== undefined,
        );

      return { effectiveSelectedEventOriginKeys, selectedEventOrigins };
    }, [selectableEvents, selectedEventOriginKeys]);

  const toggleEventSelection = useCallback(
    (eventOrigin: EventOrigin) => {
      const originKey = eventOriginKey(eventOrigin);
      setSelectedEventOriginKeys((current) => {
        const next = new Set(
          Array.from(current).filter((selectedOriginKey) =>
            selectableEvents.has(selectedOriginKey),
          ),
        );

        if (next.has(originKey)) {
          next.delete(originKey);
        } else {
          next.add(originKey);
        }
        return next;
      });
    },
    [selectableEvents],
  );

  const clearEventSelection = useCallback(() => {
    setSelectedEventOriginKeys(new Set());
  }, []);

  return {
    selectedEventOriginKeys: effectiveSelectedEventOriginKeys,
    selectedEventOrigins,
    toggleEventSelection,
    clearEventSelection,
  };
};
