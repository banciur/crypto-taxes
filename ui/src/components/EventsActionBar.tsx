"use client";

import { Button } from "react-bootstrap";

import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";

export type EventsActionFeedback = {
  tone: "success" | "danger";
  message: string;
};

type EventsActionBarProps = {
  selectedEventCount: number;
  isCorrectionChangePending: boolean;
  feedback: EventsActionFeedback | null;
  onDiscardSelected: () => void;
  onReplaceSelected: () => void;
  onAddOpeningBalance: () => void;
};

export function EventsActionBar({
  selectedEventCount,
  isCorrectionChangePending,
  feedback,
  onDiscardSelected,
  onReplaceSelected,
  onAddOpeningBalance,
}: EventsActionBarProps) {
  const { selected } = useUrlColumnSelection();
  const hasSelectableColumn = selected.has("raw") || selected.has("corrected");
  const hasCorrectionsColumn = selected.has("corrections");

  if (!hasSelectableColumn && !hasCorrectionsColumn && !feedback) {
    return null;
  }

  const selectionStatus =
    selectedEventCount === 0
      ? "Select events to discard or replace."
      : `${selectedEventCount} event${selectedEventCount === 1 ? "" : "s"} selected.`;

  return (
    <div className="flex-shrink-0 border-bottom bg-body px-3 py-2">
      <div className="d-flex flex-wrap align-items-center gap-2">
        {hasSelectableColumn && (
          <>
            <span className="small text-muted">{selectionStatus}</span>
            <Button
              type="button"
              size="sm"
              variant="warning"
              disabled={selectedEventCount === 0 || isCorrectionChangePending}
              onClick={onDiscardSelected}
            >
              Discard selected
            </Button>
            <Button
              type="button"
              size="sm"
              variant="primary"
              disabled={selectedEventCount === 0 || isCorrectionChangePending}
              onClick={onReplaceSelected}
            >
              Replace selected
            </Button>
          </>
        )}
        <Button
          type="button"
          size="sm"
          variant="outline-primary"
          disabled={isCorrectionChangePending}
          onClick={onAddOpeningBalance}
        >
          Add opening balance
        </Button>
        {feedback && (
          <span
            className={
              feedback.tone === "success"
                ? "small text-success"
                : "small text-danger"
            }
            role="status"
          >
            {feedback.message}
          </span>
        )}
      </div>
    </div>
  );
}
