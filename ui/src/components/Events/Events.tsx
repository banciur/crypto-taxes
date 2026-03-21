"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError } from "@/api/core";
import { createCorrection, deleteCorrection } from "@/api/corrections";
import {
  EventsActionBar,
  type EventsActionFeedback,
} from "@/components/EventsActionBar";
import { VirtualizedDateSections } from "@/components/VirtualizedDateSections";
import type {
  CreateLedgerCorrectionPayload,
  EventsByTimestamp,
} from "@/types/events";
import { OpeningBalanceEditorModal } from "./OpeningBalanceEditorModal";
import { ReplacementEditorModal } from "./ReplacementEditorModal";
import { useEventSelection } from "./useEventSelection";

type EventsProps = {
  eventsByTimestamp: EventsByTimestamp;
};

export function Events({ eventsByTimestamp }: EventsProps) {
  const router = useRouter();
  const [isCreatingCorrection, setIsCreatingCorrection] = useState(false);
  const [isRemovingCorrection, setIsRemovingCorrection] = useState(false);
  const [isReplacementEditorOpen, setIsReplacementEditorOpen] = useState(false);
  const [isOpeningBalanceEditorOpen, setIsOpeningBalanceEditorOpen] =
    useState(false);
  const [replacementEditorError, setReplacementEditorError] = useState<
    string | null
  >(null);
  const [openingBalanceEditorError, setOpeningBalanceEditorError] = useState<
    string | null
  >(null);
  const [feedback, setFeedback] = useState<EventsActionFeedback | null>(null);
  const {
    selectedEventOriginKeys,
    toggleEventSelection,
    clearEventSelection,
    getSelectedEvents,
  } = useEventSelection(eventsByTimestamp);

  const handleCreateDiscards = useCallback(async () => {
    const payloads: CreateLedgerCorrectionPayload[] = getSelectedEvents().map(
      (sourceEvent) => ({
        timestamp: sourceEvent.timestamp,
        sources: [sourceEvent.eventOrigin],
        legs: [],
      }),
    );

    setFeedback(null);
    setIsCreatingCorrection(true);

    const results = await Promise.allSettled(payloads.map(createCorrection));
    setIsCreatingCorrection(false);

    const failures = results.flatMap((result) =>
      result.status === "rejected" ? [result.reason] : [],
    );
    if (failures.length > 0) {
      console.error("Failed to create discard corrections", failures);
      setFeedback({
        tone: "danger",
        message:
          failures[0] instanceof ApiError
            ? failures[0].detail
            : "Saving the discard corrections failed. Check the console for details.",
      });
      return;
    }

    clearEventSelection();
    setFeedback({
      tone: "success",
      message:
        "Discard corrections saved and the corrections lane refreshed. Re-run the pipeline to refresh corrected events.",
    });
    router.refresh();
  }, [clearEventSelection, getSelectedEvents, router]);

  const handleOpenReplacementEditor = () => {
    setReplacementEditorError(null);
    setIsReplacementEditorOpen(true);
  };

  const handleCloseReplacementEditor = () => {
    setReplacementEditorError(null);
    setIsReplacementEditorOpen(false);
  };

  const handleOpenOpeningBalanceEditor = useCallback(() => {
    setOpeningBalanceEditorError(null);
    setIsOpeningBalanceEditorOpen(true);
  }, []);

  const handleCloseOpeningBalanceEditor = () => {
    setOpeningBalanceEditorError(null);
    setIsOpeningBalanceEditorOpen(false);
  };

  const handleCreateReplacement = useCallback(
    async (payload: CreateLedgerCorrectionPayload) => {
      setFeedback(null);
      setReplacementEditorError(null);
      setIsCreatingCorrection(true);

      try {
        await createCorrection(payload);
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
        setIsCreatingCorrection(false);
      }
    },
    [clearEventSelection, router],
  );

  const handleCreateOpeningBalance = useCallback(
    async (payload: CreateLedgerCorrectionPayload) => {
      setFeedback(null);
      setOpeningBalanceEditorError(null);
      setIsCreatingCorrection(true);

      try {
        await createCorrection(payload);
        setFeedback({
          tone: "success",
          message:
            "Opening balance saved and the corrections lane refreshed. Re-run the pipeline to refresh corrected events.",
        });
        setIsOpeningBalanceEditorOpen(false);
        router.refresh();
      } catch (error) {
        console.error("Failed to create opening balance correction", error);
        setOpeningBalanceEditorError(
          error instanceof ApiError
            ? error.detail
            : "Saving the opening balance failed. Check the console for details.",
        );
      } finally {
        setIsCreatingCorrection(false);
      }
    },
    [router],
  );

  const handleRemoveCorrection = useCallback(
    async (correctionId: string) => {
      setFeedback(null);
      setIsRemovingCorrection(true);

      try {
        await deleteCorrection(correctionId);
        setFeedback({
          tone: "success",
          message:
            "Correction removed and the corrections lane refreshed. Re-run the pipeline to refresh corrected events.",
        });
        router.refresh();
      } catch (error) {
        console.error("Failed to remove correction", error);
        setFeedback({
          tone: "danger",
          message:
            "Removing the correction failed. Check the console for details.",
        });
      } finally {
        setIsRemovingCorrection(false);
      }
    },
    [router],
  );

  const isCorrectionChangePending =
    isCreatingCorrection || isRemovingCorrection;

  return (
    <div className="d-flex h-100 w-100 flex-column">
      <EventsActionBar
        selectedEventCount={selectedEventOriginKeys.size}
        isCorrectionChangePending={isCorrectionChangePending}
        feedback={feedback}
        onDiscardSelected={handleCreateDiscards}
        onReplaceSelected={handleOpenReplacementEditor}
        onAddOpeningBalance={handleOpenOpeningBalanceEditor}
      />
      {isReplacementEditorOpen && (
        <ReplacementEditorModal
          show
          selectedSourceEvents={getSelectedEvents()}
          isSaving={isCreatingCorrection}
          errorMessage={replacementEditorError}
          onHide={handleCloseReplacementEditor}
          onSubmit={handleCreateReplacement}
        />
      )}
      {isOpeningBalanceEditorOpen && (
        <OpeningBalanceEditorModal
          show
          isSaving={isCreatingCorrection}
          errorMessage={openingBalanceEditorError}
          onHide={handleCloseOpeningBalanceEditor}
          onSubmit={handleCreateOpeningBalance}
        />
      )}
      <VirtualizedDateSections
        eventsByTimestamp={eventsByTimestamp}
        selectedEventOriginKeys={selectedEventOriginKeys}
        isCorrectionChangePending={isCorrectionChangePending}
        className="flex-grow-1"
        onToggleEventSelection={toggleEventSelection}
        onRemoveCorrection={handleRemoveCorrection}
      />
    </div>
  );
}
