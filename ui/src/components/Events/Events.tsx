"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createSpamCorrection,
  deleteSpamCorrection,
} from "@/api/spamCorrections";
import {
  EventsActionBar,
  type EventsActionFeedback,
} from "@/components/EventsActionBar";
import { VirtualizedDateSections } from "@/components/VirtualizedDateSections";
import { eventOriginKey } from "@/lib/eventOrigin";
import type { EventOrigin, EventsByTimestamp } from "@/types/events";
import { collectSelectableEventOrigins } from "./selectableEvents";

type EventsProps = {
  eventsByTimestamp: EventsByTimestamp;
};

export function Events({ eventsByTimestamp }: EventsProps) {
  const [selectedEventOriginKeys, setSelectedEventOriginKeys] = useState<
    Set<string>
  >(() => new Set());
  const [isMarkingSpam, setIsMarkingSpam] = useState(false);
  const [isRemovingSpamCorrection, setIsRemovingSpamCorrection] =
    useState(false);
  const [feedback, setFeedback] = useState<EventsActionFeedback | null>(null);

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

  const handleToggleEventSelection = useCallback(
    (eventOrigin: EventOrigin) => {
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
    },
    [],
  );

  const handleMarkSelectedAsSpam = useCallback(async () => {
    if (selectedEventOrigins.length === 0) {
      return;
    }

    setFeedback(null);
    setIsMarkingSpam(true);

    const results = await Promise.allSettled(
      selectedEventOrigins.map((eventOrigin) => createSpamCorrection(eventOrigin)),
    );

    setIsMarkingSpam(false);

    const failures = results.flatMap((result) =>
      result.status === "rejected" ? [result.reason] : [],
    );
    if (failures.length > 0) {
      console.error("Failed to create spam corrections", failures);
      setFeedback({
        tone: "danger",
        message:
          "Some spam markers failed. Check the console, then rerun the pipeline manually if needed.",
      });
      return;
    }

    setSelectedEventOriginKeys(new Set());
    setFeedback({
      tone: "success",
      message:
        "Spam markers saved. Re-run the pipeline and reload the UI to refresh the lanes.",
    });
  }, [selectedEventOrigins]);

  const handleRemoveSpamCorrection = useCallback(
    async (eventOrigin: EventOrigin) => {
      setFeedback(null);
      setIsRemovingSpamCorrection(true);

      try {
        await deleteSpamCorrection(eventOrigin);
        setFeedback({
          tone: "success",
          message:
            "Spam marker removed. Re-run the pipeline and reload the UI to refresh the lanes.",
        });
      } catch (error) {
        console.error("Failed to remove spam correction", error);
        setFeedback({
          tone: "danger",
          message:
            "Removing the spam marker failed. Check the console for details.",
        });
      } finally {
        setIsRemovingSpamCorrection(false);
      }
    },
    [],
  );

  return (
    <div className="d-flex h-100 w-100 flex-column">
      <EventsActionBar
        selectedEventCount={selectedEventOrigins.length}
        isRemovingSpamCorrection={isRemovingSpamCorrection}
        isMarkingSpam={isMarkingSpam}
        feedback={feedback}
        onMarkSelectedAsSpam={handleMarkSelectedAsSpam}
      />
      <VirtualizedDateSections
        eventsByTimestamp={eventsByTimestamp}
        selectedEventOriginKeys={selectedEventOriginKeys}
        isSpamMarkerChangePending={isMarkingSpam || isRemovingSpamCorrection}
        className="flex-grow-1"
        onToggleEventSelection={handleToggleEventSelection}
        onRemoveSpamCorrection={handleRemoveSpamCorrection}
      />
    </div>
  );
}
