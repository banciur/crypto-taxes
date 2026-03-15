"use client";

import { useCallback, useState } from "react";

import {
  createSpamCorrection,
  deleteSpamCorrection,
} from "@/api/spamCorrections";
import {
  EventsActionBar,
  type EventsActionFeedback,
} from "@/components/EventsActionBar";
import { VirtualizedDateSections } from "@/components/VirtualizedDateSections";
import type { EventOrigin, EventsByTimestamp } from "@/types/events";
import { useEventSelection } from "./useEventSelection";

type EventsProps = {
  eventsByTimestamp: EventsByTimestamp;
};

export function Events({ eventsByTimestamp }: EventsProps) {
  const [isMarkingSpam, setIsMarkingSpam] = useState(false);
  const [isRemovingSpamCorrection, setIsRemovingSpamCorrection] =
    useState(false);
  const [feedback, setFeedback] = useState<EventsActionFeedback | null>(null);
  const {
    selectedEventOriginKeys,
    selectedEventOrigins,
    toggleEventSelection,
    clearEventSelection,
  } = useEventSelection(eventsByTimestamp);

  const handleMarkSelectedAsSpam = useCallback(async () => {
    if (selectedEventOrigins.length === 0) {
      return;
    }

    setFeedback(null);
    setIsMarkingSpam(true);

    const results = await Promise.allSettled(
      selectedEventOrigins.map((eventOrigin) =>
        createSpamCorrection(eventOrigin),
      ),
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

    clearEventSelection();
    setFeedback({
      tone: "success",
      message:
        "Spam markers saved. Re-run the pipeline and reload the UI to refresh the lanes.",
    });
  }, [clearEventSelection, selectedEventOrigins]);

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
        onToggleEventSelection={toggleEventSelection}
        onRemoveSpamCorrection={handleRemoveSpamCorrection}
      />
    </div>
  );
}
