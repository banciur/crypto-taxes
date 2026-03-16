"use client";

import { useCallback, useMemo, useState } from "react";

import { eventOriginKey } from "@/lib/eventOrigin";
import type { EventOrigin, EventsByTimestamp } from "@/types/events";
import { collectSelectableEventOriginKeys } from "./selectableEvents";

type UseEventSelectionResult = {
  selectedEventOriginKeys: ReadonlySet<string>;
  selectedEvents: readonly EventOrigin[];
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

  const selectedEvents = useMemo(() => {
    const pendingSelectedEventOriginKeys = new Set(
      effectiveSelectedEventOriginKeys,
    );
    const nextSelectedEvents: EventOrigin[] = [];

    for (const columnsByTimestamp of Object.values(eventsByTimestamp)) {
      for (const columnItems of Object.values(columnsByTimestamp)) {
        if (!columnItems) {
          continue;
        }

        for (const item of columnItems) {
          if (
            item.kind !== "raw-event" &&
            item.kind !== "corrected-event"
          ) {
            continue;
          }

          const originKey = eventOriginKey(item.eventOrigin);
          if (!pendingSelectedEventOriginKeys.has(originKey)) {
            continue;
          }

          nextSelectedEvents.push(item.eventOrigin);
          pendingSelectedEventOriginKeys.delete(originKey);

          if (pendingSelectedEventOriginKeys.size === 0) {
            return nextSelectedEvents;
          }
        }
      }
    }

    return nextSelectedEvents;
  }, [effectiveSelectedEventOriginKeys, eventsByTimestamp]);

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
    selectedEventOriginKeys: new Set(effectiveSelectedEventOriginKeys),
    selectedEvents,
    toggleEventSelection,
    clearEventSelection,
  };
};
