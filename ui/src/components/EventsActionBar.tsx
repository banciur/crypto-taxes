"use client";

import { Button, Spinner } from "react-bootstrap";

import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";

export type EventsActionFeedback = {
  tone: "success" | "danger";
  message: string;
};

type EventsActionBarProps = {
  selectedEventCount: number;
  isRemovingSpamCorrection: boolean;
  isMarkingSpam: boolean;
  feedback: EventsActionFeedback | null;
  onMarkSelectedAsSpam: () => void;
};

export function EventsActionBar({
  selectedEventCount,
  isRemovingSpamCorrection,
  isMarkingSpam,
  feedback,
  onMarkSelectedAsSpam,
}: EventsActionBarProps) {
  const { selected } = useUrlColumnSelection();
  const hasRawColumn = selected.has("raw");

  if (!hasRawColumn && !feedback) {
    return null;
  }

  const selectionStatus =
    selectedEventCount === 0
      ? "Select raw events to create spam markers."
      : `${selectedEventCount} raw event${selectedEventCount === 1 ? "" : "s"} selected.`;

  return (
    <div className="flex-shrink-0 border-bottom bg-body px-3 py-2">
      <div className="d-flex flex-wrap align-items-center gap-2">
        {hasRawColumn && (
          <>
            <span className="small text-muted">{selectionStatus}</span>
            <Button
              type="button"
              size="sm"
              variant="warning"
              disabled={
                selectedEventCount === 0 ||
                isMarkingSpam ||
                isRemovingSpamCorrection
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
