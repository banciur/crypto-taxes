"use client";

import { useCallback, useMemo, useState } from "react";

import { eventOriginKey } from "@/lib/eventOrigin";
import type { EventOrigin, EventsByTimestamp } from "@/types/events";
import { collectSelectableEvents } from "./selectableEvents";

type UseEventSelectionResult = {
  selectedEvents: ReadonlyMap<string, EventOrigin>;
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

  const selectedEvents = useMemo(() => {
    const effectiveSelectedEventOriginKeys = new Set(
      Array.from(selectedEventOriginKeys).filter((originKey) =>
        selectableEvents.has(originKey),
      ),
    );

    const selectedEvents = new Map<string, EventOrigin>();

    for (const originKey of effectiveSelectedEventOriginKeys) {
      const eventOrigin = selectableEvents.get(originKey);
      if (eventOrigin) {
        selectedEvents.set(originKey, eventOrigin);
      }
    }

    return selectedEvents;
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
    selectedEvents,
    toggleEventSelection,
    clearEventSelection,
  };
};
