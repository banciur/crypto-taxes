"use client";

import { useCallback, useMemo, useState } from "react";

import { deleteReplacementCorrection } from "@/api/replacementCorrections";
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
import { resolveSelectedSourceEvents } from "./selectableEvents";
import { useEventSelection } from "./useEventSelection";

type EventsProps = {
  eventsByTimestamp: EventsByTimestamp;
};

export function Events({ eventsByTimestamp }: EventsProps) {
  const [isMarkingSpam, setIsMarkingSpam] = useState(false);
  const [isRemovingSpamCorrection, setIsRemovingSpamCorrection] =
    useState(false);
  const [isRemovingReplacementCorrection, setIsRemovingReplacementCorrection] =
    useState(false);
  const [feedback, setFeedback] = useState<EventsActionFeedback | null>(null);
  const { selectedEventOriginKeys, toggleEventSelection, clearEventSelection } =
    useEventSelection(eventsByTimestamp);
  const selectedSourceEvents = useMemo(
    () =>
      resolveSelectedSourceEvents(eventsByTimestamp, selectedEventOriginKeys),
    [eventsByTimestamp, selectedEventOriginKeys],
  );

  const handleMarkSelectedAsSpam = useCallback(async () => {
    if (selectedSourceEvents.length === 0) {
      return;
    }

    setFeedback(null);
    setIsMarkingSpam(true);

    const results = await Promise.allSettled(
      selectedSourceEvents.map((sourceEvent) =>
        createSpamCorrection(sourceEvent.eventOrigin),
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
  }, [clearEventSelection, selectedSourceEvents]);

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

  const handleRemoveReplacementCorrection = useCallback(
    async (correctionId: string) => {
      setFeedback(null);
      setIsRemovingReplacementCorrection(true);

      try {
        await deleteReplacementCorrection(correctionId);
        setFeedback({
          tone: "success",
          message:
            "Replacement removed. Re-run the pipeline and reload the UI to refresh the lanes.",
        });
      } catch (error) {
        console.error("Failed to remove replacement correction", error);
        setFeedback({
          tone: "danger",
          message:
            "Removing the replacement failed. Check the console for details.",
        });
      } finally {
        setIsRemovingReplacementCorrection(false);
      }
    },
    [],
  );

  const isCorrectionChangePending =
    isMarkingSpam ||
    isRemovingSpamCorrection ||
    isRemovingReplacementCorrection;

  return (
    <div className="d-flex h-100 w-100 flex-column">
      <EventsActionBar
        selectedEventCount={selectedEventOriginKeys.size}
        isCorrectionChangePending={isCorrectionChangePending}
        isMarkingSpam={isMarkingSpam}
        feedback={feedback}
        onMarkSelectedAsSpam={handleMarkSelectedAsSpam}
      />
      <VirtualizedDateSections
        eventsByTimestamp={eventsByTimestamp}
        selectedEventOriginKeys={selectedEventOriginKeys}
        isCorrectionChangePending={isCorrectionChangePending}
        className="flex-grow-1"
        onToggleEventSelection={toggleEventSelection}
        onRemoveSpamCorrection={handleRemoveSpamCorrection}
        onRemoveReplacementCorrection={handleRemoveReplacementCorrection}
      />
    </div>
  );
}
