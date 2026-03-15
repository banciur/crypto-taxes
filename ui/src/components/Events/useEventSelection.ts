"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { eventOriginKey } from "@/lib/eventOrigin";
import type { EventOrigin, EventsByTimestamp } from "@/types/events";
import { collectSelectableEventOrigins } from "./selectableEvents";

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

  const { selectableEventOrigins, selectableEventOriginKeys } = useMemo(
    () => collectSelectableEventOrigins(eventsByTimestamp),
    [eventsByTimestamp],
  );

  const selectedEventOrigins = useMemo(
    () =>
      selectableEventOrigins.filter((eventOrigin) =>
        selectedEventOriginKeys.has(eventOriginKey(eventOrigin)),
      ),
    [selectableEventOrigins, selectedEventOriginKeys],
  );

  useEffect(() => {
    setSelectedEventOriginKeys((current) => {
      if (current.size === 0) {
        return current;
      }

      const next = new Set(
        Array.from(current).filter((originKey) =>
          selectableEventOriginKeys.has(originKey),
        ),
      );
      if (next.size === current.size) {
        return current;
      }
      return next;
    });
  }, [selectableEventOriginKeys]);

  const toggleEventSelection = useCallback((eventOrigin: EventOrigin) => {
    const originKey = eventOriginKey(eventOrigin);
    setSelectedEventOriginKeys((current) => {
      const next = new Set(current);

      if (next.has(originKey)) {
        next.delete(originKey);
      } else {
        next.add(originKey);
      }
      return next;
    });
  }, []);

  const clearEventSelection = useCallback(() => {
    setSelectedEventOriginKeys(new Set());
  }, []);

  return {
    selectedEventOriginKeys,
    selectedEventOrigins,
    toggleEventSelection,
    clearEventSelection,
  };
};
