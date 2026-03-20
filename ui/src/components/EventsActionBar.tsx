"use client";

import { Button, Spinner } from "react-bootstrap";

import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";

export type EventsActionFeedback = {
  tone: "success" | "danger";
  message: string;
};

type EventsActionBarProps = {
  selectedEventCount: number;
  isCorrectionChangePending: boolean;
  isMarkingSpam: boolean;
  feedback: EventsActionFeedback | null;
  onMarkSelectedAsSpam: () => void;
  onReplaceSelected: () => void;
};

export function EventsActionBar({
  selectedEventCount,
  isCorrectionChangePending,
  isMarkingSpam,
  feedback,
  onMarkSelectedAsSpam,
  onReplaceSelected,
}: EventsActionBarProps) {
  const { selected } = useUrlColumnSelection();
  const hasSelectableColumn = selected.has("raw") || selected.has("corrected");

  if (!hasSelectableColumn && !feedback) {
    return null;
  }

  const selectionStatus =
    selectedEventCount === 0
      ? "Select events to create spam markers or replacements."
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
              disabled={
                selectedEventCount === 0 ||
                isMarkingSpam ||
                isCorrectionChangePending
              }
              onClick={onMarkSelectedAsSpam}
            >
              {isMarkingSpam ? (
                <>
                  <Spinner size="sm" className="me-2" />
                  Marking...
                </>
              ) : (
                "Mark as spam"
              )}
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
