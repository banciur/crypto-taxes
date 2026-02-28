"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ColumnKey } from "@/consts";
import { orderColumnKeys } from "@/consts";

import { useVirtualizer } from "@tanstack/react-virtual";
import { Button, Col, Row, Spinner } from "react-bootstrap";
import { LaneItem } from "@/components/LaneItem";
import { useVisibleDay } from "@/contexts/VisibleDayContext";
import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";
import { dayIdFor } from "@/lib/dayHash";
import type {
  EventOriginData,
  LaneItemData,
  RawEventCardData,
  SpamCorrectionItemData,
} from "@/types/events";

type EventsByDate = Record<string, Partial<Record<ColumnKey, LaneItemData[]>>>;

type EventsProps = {
  eventsByDate: EventsByDate;
};

type ActionFeedback = {
  tone: "success" | "danger";
  message: string;
};

const isRawEvent = (item: LaneItemData): item is RawEventCardData =>
  item.kind === "raw-event";

const buildSpamCorrectionPayload = (eventOrigin: EventOriginData) => ({
  event_origin: {
    location: eventOrigin.location,
    external_id: eventOrigin.externalId,
  },
});

const readFailureDetails = async (response: Response) => {
  const details = await response.text().catch(() => "missing details");
  return details || "missing details";
};

const createSpamCorrection = async (eventOrigin: EventOriginData) => {
  const response = await fetch("/spam-corrections", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(buildSpamCorrectionPayload(eventOrigin)),
  });

  if (!response.ok) {
    const details = await readFailureDetails(response);
    throw new Error(
      `POST /spam-corrections failed for ${eventOrigin.location}/${eventOrigin.externalId}: ${response.status} : ${details}`,
    );
  }
};

const deleteSpamCorrection = async (eventOrigin: EventOriginData) => {
  const response = await fetch("/spam-corrections", {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(buildSpamCorrectionPayload(eventOrigin)),
  });

  if (!response.ok) {
    const details = await readFailureDetails(response);
    throw new Error(
      `DELETE /spam-corrections failed for ${eventOrigin.location}/${eventOrigin.externalId}: ${response.status} : ${details}`,
    );
  }
};

export function Events({ eventsByDate }: EventsProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { selected } = useUrlColumnSelection();
  const { activeDayKey, activeDaySource, setActiveDayKey } = useVisibleDay();
  const [selectedRawEventIds, setSelectedRawEventIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [isMarkingSpam, setIsMarkingSpam] = useState(false);
  const [removingSpamCorrectionId, setRemovingSpamCorrectionId] = useState<
    string | null
  >(null);
  const [feedback, setFeedback] = useState<ActionFeedback | null>(null);

  const dates = useMemo(() => Object.keys(eventsByDate), [eventsByDate]);
  const orderedSelectedColumns = useMemo(
    () => orderColumnKeys(selected),
    [selected],
  );
  const hasRawColumn = orderedSelectedColumns.includes("raw");
  const rawEventsById = useMemo(() => {
    const items = new Map<string, RawEventCardData>();

    for (const columnsByDate of Object.values(eventsByDate)) {
      for (const columnItems of Object.values(columnsByDate)) {
        if (!columnItems) {
          continue;
        }

        for (const item of columnItems) {
          if (isRawEvent(item)) {
            items.set(item.id, item);
          }
        }
      }
    }

    return items;
  }, [eventsByDate]);
  const selectedRawEvents = useMemo(
    () =>
      Array.from(selectedRawEventIds)
        .map((eventId) => rawEventsById.get(eventId))
        .filter((item): item is RawEventCardData => item !== undefined),
    [rawEventsById, selectedRawEventIds],
  );
  const hasPendingAction = isMarkingSpam || removingSpamCorrectionId !== null;

  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: dates.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 110,
    gap: 16,
    overscan: 5,
    onChange: (instance, sync) => {
      if (sync) return;
      updateVisibleDay(instance.getVirtualItems());
    },
  });

  const updateVisibleDay = useCallback(
    (items: ReturnType<typeof virtualizer.getVirtualItems>) => {
      const scrollElement = containerRef.current;
      if (!scrollElement || items.length === 0) return;

      const scrollTop = scrollElement.scrollTop;
      let visibleItem = items.find(
        (item) => item.start <= scrollTop && item.end > scrollTop,
      );

      if (!visibleItem) {
        if (scrollTop <= 0) {
          visibleItem = items[0];
        } else {
          visibleItem = items.find((item) => item.start > scrollTop);
        }
      }

      if (!visibleItem) {
        visibleItem = items[items.length - 1];
      }

      const dateKey = dates[visibleItem.index];
      if (!dateKey) return;
      setActiveDayKey(dateKey, "scroll");
    },
    [dates, setActiveDayKey, virtualizer],
  );

  useEffect(() => {
    setSelectedRawEventIds((current) => {
      if (current.size === 0) {
        return current;
      }

      const next = new Set(
        Array.from(current).filter((eventId) => rawEventsById.has(eventId)),
      );
      if (next.size === current.size) {
        return current;
      }
      return next;
    });
  }, [rawEventsById]);

  useEffect(() => {
    if (
      !activeDayKey ||
      activeDaySource === "scroll" ||
      !containerRef.current
    ) {
      return;
    }

    const index = dates.findIndex((element) => element === activeDayKey);
    if (index === -1) return;
    virtualizer.scrollToIndex(index, { align: "start" });
  }, [activeDayKey, activeDaySource, dates, virtualizer]);

  const items = virtualizer.getVirtualItems();

  const handleRawSelectionChange = useCallback(
    (eventId: string, isSelected: boolean) => {
      setFeedback(null);
      setSelectedRawEventIds((current) => {
        const next = new Set(current);
        if (isSelected) {
          next.add(eventId);
        } else {
          next.delete(eventId);
        }
        return next;
      });
    },
    [],
  );

  const handleMarkSelectedAsSpam = useCallback(async () => {
    if (selectedRawEvents.length === 0) {
      return;
    }

    setFeedback(null);
    setIsMarkingSpam(true);

    const results = await Promise.allSettled(
      selectedRawEvents.map((event) => createSpamCorrection(event.eventOrigin)),
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

    setSelectedRawEventIds(new Set());
    setFeedback({
      tone: "success",
      message:
        "Spam markers saved. Re-run the pipeline and reload the UI to refresh the lanes.",
    });
  }, [selectedRawEvents]);

  const handleRemoveSpamCorrection = useCallback(
    async (item: SpamCorrectionItemData) => {
      setFeedback(null);
      setRemovingSpamCorrectionId(item.id);

      try {
        await deleteSpamCorrection(item.eventOrigin);
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
        setRemovingSpamCorrectionId(null);
      }
    },
    [],
  );

  return (
    <div className="d-flex h-100 w-100 flex-column">
      {(hasRawColumn || feedback) && (
        <div className="flex-shrink-0 border-bottom bg-body px-3 py-2">
          <div className="d-flex flex-wrap align-items-center gap-2">
            {hasRawColumn ? (
              <>
                <span className="small text-muted">
                  {selectedRawEvents.length === 0
                    ? "Select raw events to create spam markers."
                    : `${selectedRawEvents.length} raw event${selectedRawEvents.length === 1 ? "" : "s"} selected.`}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="warning"
                  disabled={selectedRawEvents.length === 0 || hasPendingAction}
                  onClick={handleMarkSelectedAsSpam}
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
            ) : null}
            {feedback ? (
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
            ) : null}
          </div>
        </div>
      )}
      <div
        ref={containerRef}
        className="flex-grow-1"
        style={{
          width: "100%",
          overflowY: "auto",
        }}
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: "100%",
            position: "relative",
          }}
        >
          {items.map((virtualRow) => {
            const dateKey = dates[virtualRow.index];
            return (
              <Row
                key={dateKey}
                id={dayIdFor(dateKey)}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <Col>
                  <h5>{dateKey}</h5>
                  <Row>
                    {orderedSelectedColumns.map((columnKey) => (
                      <Col
                        className="d-flex flex-column gap-2"
                        key={`row-${virtualRow.index}-${columnKey}`}
                      >
                        {eventsByDate[dateKey][columnKey]?.map((item) => (
                          <LaneItem
                            key={item.id}
                            item={item}
                            isSelected={selectedRawEventIds.has(item.id)}
                            rawSelectionDisabled={hasPendingAction}
                            onRawSelectionChange={(isSelected) =>
                              handleRawSelectionChange(item.id, isSelected)
                            }
                            onRemoveSpamCorrection={handleRemoveSpamCorrection}
                            spamActionDisabled={hasPendingAction}
                            isRemovingSpamCorrection={
                              removingSpamCorrectionId === item.id
                            }
                          />
                        ))}
                      </Col>
                    ))}
                  </Row>
                </Col>
              </Row>
            );
          })}
        </div>
      </div>
    </div>
  );
}
