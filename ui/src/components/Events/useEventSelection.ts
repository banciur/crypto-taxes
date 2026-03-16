"use client";

import { useCallback, useMemo, useState } from "react";

import { eventOriginKey } from "@/lib/eventOrigin";
import type { EventsByTimestamp } from "@/types/events";
import {
  collectSelectableEvents,
  type SelectableEvent,
} from "./selectableEvents";

type UseEventSelectionResult = {
  selectedEvents: ReadonlyMap<string, SelectableEvent>;
  toggleEventSelection: (event: SelectableEvent) => void;
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

    const selectedEvents = new Map<string, SelectableEvent>();

    for (const originKey of effectiveSelectedEventOriginKeys) {
      const selectedEvent = selectableEvents.get(originKey);
      if (selectedEvent) {
        selectedEvents.set(originKey, selectedEvent);
      }
    }

    return selectedEvents;
  }, [selectableEvents, selectedEventOriginKeys]);

  const toggleEventSelection = useCallback(
    (event: SelectableEvent) => {
      const originKey = eventOriginKey(event.eventOrigin);
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
