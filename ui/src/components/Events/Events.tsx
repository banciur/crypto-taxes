"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError } from "@/api/core";
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
import type { EventOrigin, EventsByTimestamp } from "@/types/events";
import type { CreateReplacementCorrectionPayload } from "@/types/events";
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
  const [replacementEditorError, setReplacementEditorError] = useState<
    string | null
  >(null);
  const [feedback, setFeedback] = useState<EventsActionFeedback | null>(null);
  const {
    selectedEventOriginKeys,
    toggleEventSelection,
    clearEventSelection,
    getSelectedEvents,
  } = useEventSelection(eventsByTimestamp);

  const handleMarkSelectedAsSpam = useCallback(async () => {
    const selectedSourceEvents = getSelectedEvents();
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
        "Spam markers saved and the corrections lane refreshed. Re-run the pipeline to refresh corrected events.",
    });
    router.refresh();
  }, [clearEventSelection, getSelectedEvents, router]);

  const handleOpenReplacementEditor = useCallback(() => {
    const selectedSourceEvents = getSelectedEvents();
    if (selectedSourceEvents.length === 0) {
      return;
    }

    setReplacementEditorError(null);
    setIsReplacementEditorOpen(true);
  }, [getSelectedEvents]);

  const handleCloseReplacementEditor = useCallback(() => {
    if (isCreatingReplacement) {
      return;
    }

    setReplacementEditorError(null);
    setIsReplacementEditorOpen(false);
  }, [isCreatingReplacement]);

  const handleCreateReplacement = useCallback(
    async (payload: CreateReplacementCorrectionPayload) => {
      setFeedback(null);
      setReplacementEditorError(null);
      setIsCreatingReplacement(true);

      try {
        await createReplacementCorrection(payload);
        clearEventSelection();
        setIsReplacementEditorOpen(false);
        setFeedback({
          tone: "success",
          message:
            "Replacement saved and the corrections lane refreshed. Re-run the pipeline to refresh corrected events.",
        });
        router.refresh();
      } catch (error) {
        console.error("Failed to create replacement correction", error);
        setReplacementEditorError(
          error instanceof ApiError
            ? error.detail
            : "Saving the replacement failed. Check the console for details.",
        );
      } finally {
        setIsCreatingReplacement(false);
      }
    },
    [clearEventSelection, router],
  );

  const handleRemoveSpamCorrection = useCallback(
    async (eventOrigin: EventOrigin) => {
      setFeedback(null);
      setIsRemovingSpamCorrection(true);

      try {
        await deleteSpamCorrection(eventOrigin);
        setFeedback({
          tone: "success",
          message:
            "Spam marker removed and the corrections lane refreshed. Re-run the pipeline to refresh corrected events.",
        });
        router.refresh();
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
            "Replacement removed and the corrections lane refreshed. Re-run the pipeline to refresh corrected events.",
        });
        router.refresh();
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
    [router],
  );

  const isCorrectionChangePending =
    isMarkingSpam ||
    isRemovingSpamCorrection ||
    isRemovingReplacementCorrection ||
    isCreatingReplacement;

  return (
    <div className="d-flex h-100 w-100 flex-column">
      <EventsActionBar
        selectedEventCount={selectedEventOriginKeys.size}
        isCorrectionChangePending={isCorrectionChangePending}
        isMarkingSpam={isMarkingSpam}
        feedback={feedback}
        onMarkSelectedAsSpam={handleMarkSelectedAsSpam}
        onReplaceSelected={handleOpenReplacementEditor}
      />
      {isReplacementEditorOpen && (
        <ReplacementEditorModal
          show
          selectedSourceEvents={getSelectedEvents()}
          isSaving={isCreatingReplacement}
          errorMessage={replacementEditorError}
          onHide={handleCloseReplacementEditor}
          onSubmit={handleCreateReplacement}
        />
      )}
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
