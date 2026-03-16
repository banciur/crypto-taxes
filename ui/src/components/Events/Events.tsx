"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { getApiErrorMessage } from "@/api/core";
import {
  createReplacementCorrection,
  deleteReplacementCorrection,
} from "@/api/replacementCorrections";
import {
  createSpamCorrection,
  deleteSpamCorrection,
} from "@/api/spamCorrections";
import {
  EventsActionBar,
  type EventsActionFeedback,
} from "@/components/EventsActionBar";
import { VirtualizedDateSections } from "@/components/VirtualizedDateSections";
import type {
  EventOrigin,
  EventsByTimestamp,
  ReplacementCorrectionCreatePayload,
} from "@/types/events";
import { ReplacementEditorModal } from "./ReplacementEditorModal";
import { useEventSelection } from "./useEventSelection";

type EventsProps = {
  eventsByTimestamp: EventsByTimestamp;
};

export function Events({ eventsByTimestamp }: EventsProps) {
  const router = useRouter();
  const [isMarkingSpam, setIsMarkingSpam] = useState(false);
  const [isRemovingSpamCorrection, setIsRemovingSpamCorrection] =
    useState(false);
  const [isRemovingReplacementCorrection, setIsRemovingReplacementCorrection] =
    useState(false);
  const [isCreatingReplacement, setIsCreatingReplacement] = useState(false);
  const [isReplacementEditorOpen, setIsReplacementEditorOpen] = useState(false);
  const [feedback, setFeedback] = useState<EventsActionFeedback | null>(null);
  const { selectedEvents, toggleEventSelection, clearEventSelection } =
    useEventSelection(eventsByTimestamp);
  const selectedEventList = useMemo(
    () => Array.from(selectedEvents.values()),
    [selectedEvents],
  );
  const replacementEditorKey = useMemo(
    () =>
      selectedEventList
        .map(
          (event) =>
            `${event.eventOrigin.location}:${event.eventOrigin.externalId}`,
        )
        .sort()
        .join("|"),
    [selectedEventList],
  );

  const handleMarkSelectedAsSpam = useCallback(async () => {
    if (selectedEvents.size === 0) {
      return;
    }

    setFeedback(null);
    setIsMarkingSpam(true);

    const results = await Promise.allSettled(
      Array.from(selectedEvents.values()).map((event) =>
        createSpamCorrection(event.eventOrigin),
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
        "Spam markers saved. The corrections lane has been refreshed. Re-run the pipeline to refresh corrected events.",
    });
    router.refresh();
  }, [clearEventSelection, router, selectedEvents]);

  const handleRemoveSpamCorrection = useCallback(
    async (eventOrigin: EventOrigin) => {
      setFeedback(null);
      setIsRemovingSpamCorrection(true);

      try {
        await deleteSpamCorrection(eventOrigin);
        setFeedback({
          tone: "success",
          message:
            "Spam marker removed. The corrections lane has been refreshed. Re-run the pipeline to refresh corrected events.",
        });
        router.refresh();
      } catch (error) {
        console.error("Failed to remove spam correction", error);
        setFeedback({
          tone: "danger",
          message: getApiErrorMessage(error),
        });
      } finally {
        setIsRemovingSpamCorrection(false);
      }
    },
    [router],
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
            "Replacement removed. The corrections lane has been refreshed. Re-run the pipeline to refresh corrected events.",
        });
        router.refresh();
      } catch (error) {
        console.error("Failed to remove replacement correction", error);
        setFeedback({
          tone: "danger",
          message: getApiErrorMessage(error),
        });
      } finally {
        setIsRemovingReplacementCorrection(false);
      }
    },
    [router],
  );

  const handleReplaceSelected = useCallback(() => {
    if (selectedEvents.size === 0) {
      return;
    }

    setFeedback(null);
    setIsReplacementEditorOpen(true);
  }, [selectedEvents.size]);

  const handleCreateReplacement = useCallback(
    async (payload: ReplacementCorrectionCreatePayload) => {
      setFeedback(null);
      setIsCreatingReplacement(true);

      try {
        await createReplacementCorrection(payload);
        clearEventSelection();
        setIsReplacementEditorOpen(false);
        setFeedback({
          tone: "success",
          message:
            "Replacement saved. The corrections lane has been refreshed. Re-run the pipeline to refresh corrected events.",
        });
        router.refresh();
      } catch (error) {
        console.error("Failed to create replacement correction", error);
        throw error;
      } finally {
        setIsCreatingReplacement(false);
      }
    },
    [clearEventSelection, router],
  );

  const isCorrectionChangePending =
    isMarkingSpam ||
    isRemovingSpamCorrection ||
    isRemovingReplacementCorrection ||
    isCreatingReplacement;

  return (
    <div className="d-flex h-100 w-100 flex-column">
      <EventsActionBar
        selectedEventCount={selectedEvents.size}
        isCorrectionChangePending={isCorrectionChangePending}
        isMarkingSpam={isMarkingSpam}
        isCreatingReplacement={isCreatingReplacement}
        feedback={feedback}
        onMarkSelectedAsSpam={handleMarkSelectedAsSpam}
        onReplaceSelected={handleReplaceSelected}
      />
      <VirtualizedDateSections
        eventsByTimestamp={eventsByTimestamp}
        selectedEvents={selectedEvents}
        isCorrectionChangePending={isCorrectionChangePending}
        className="flex-grow-1"
        onToggleEventSelection={toggleEventSelection}
        onRemoveSpamCorrection={handleRemoveSpamCorrection}
        onRemoveReplacementCorrection={handleRemoveReplacementCorrection}
      />
      {isReplacementEditorOpen ? (
        <ReplacementEditorModal
          key={replacementEditorKey}
          show
          selectedEvents={selectedEventList}
          isSubmitting={isCreatingReplacement}
          onHide={() => setIsReplacementEditorOpen(false)}
          onSubmit={handleCreateReplacement}
        />
      ) : null}
    </div>
  );
}
