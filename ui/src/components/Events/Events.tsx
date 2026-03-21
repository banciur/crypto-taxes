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
  const [isCreatingDiscard, setIsCreatingDiscard] = useState(false);
  const [isRemovingCorrection, setIsRemovingCorrection] = useState(false);
  const [isCreatingReplacement, setIsCreatingReplacement] = useState(false);
  const [isCreatingOpeningBalance, setIsCreatingOpeningBalance] =
    useState(false);
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
    const selectedSourceEvents = getSelectedEvents();

    const payloads: CreateLedgerCorrectionPayload[] = selectedSourceEvents.map(
      (sourceEvent) => ({
        timestamp: sourceEvent.timestamp,
        sources: [sourceEvent.eventOrigin],
        legs: [],
        note: null,
      }),
    );

    setFeedback(null);
    setIsCreatingDiscard(true);

    const results = await Promise.allSettled(
      payloads.map((payload) => createCorrection(payload)),
    );

    setIsCreatingDiscard(false);

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

  const handleOpenOpeningBalanceEditor = useCallback(() => {
    setOpeningBalanceEditorError(null);
    setIsOpeningBalanceEditorOpen(true);
  }, []);

  const handleCloseOpeningBalanceEditor = useCallback(() => {
    if (isCreatingOpeningBalance) {
      return;
    }

    setOpeningBalanceEditorError(null);
    setIsOpeningBalanceEditorOpen(false);
  }, [isCreatingOpeningBalance]);

  const handleCreateReplacement = useCallback(
    async (payload: CreateLedgerCorrectionPayload) => {
      setFeedback(null);
      setReplacementEditorError(null);
      setIsCreatingReplacement(true);

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
        setIsCreatingReplacement(false);
      }
    },
    [clearEventSelection, router],
  );

  const handleCreateOpeningBalance = useCallback(
    async (payload: CreateLedgerCorrectionPayload) => {
      setFeedback(null);
      setOpeningBalanceEditorError(null);
      setIsCreatingOpeningBalance(true);

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
        setIsCreatingOpeningBalance(false);
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
    isCreatingDiscard ||
    isRemovingCorrection ||
    isCreatingReplacement ||
    isCreatingOpeningBalance;

  return (
    <div className="d-flex h-100 w-100 flex-column">
      <EventsActionBar
        selectedEventCount={selectedEventOriginKeys.size}
        isCorrectionChangePending={isCorrectionChangePending}
        isCreatingDiscard={isCreatingDiscard}
        feedback={feedback}
        onDiscardSelected={handleCreateDiscards}
        onReplaceSelected={handleOpenReplacementEditor}
        onAddOpeningBalance={handleOpenOpeningBalanceEditor}
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
      {isOpeningBalanceEditorOpen && (
        <OpeningBalanceEditorModal
          show
          isSaving={isCreatingOpeningBalance}
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
