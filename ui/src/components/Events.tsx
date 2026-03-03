"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createSpamCorrection,
  deleteSpamCorrection,
} from "@/api/spamCorrections";
import {
  EventsActionBar,
  type EventsActionFeedback,
} from "@/components/EventsActionBar";
import { VirtualizedDateSections } from "@/components/VirtualizedDateSections";
import { eventOriginKey } from "@/lib/eventOrigin";
import type {
  EventOrigin,
  EventsByDate,
  LaneItemData,
  RawEventCardData,
} from "@/types/events";

type EventsProps = {
  eventsByDate: EventsByDate;
};

const isRawEvent = (item: LaneItemData): item is RawEventCardData =>
  item.kind === "raw-event";

export function Events({ eventsByDate }: EventsProps) {
  const [selectedRawEventOriginKeys, setSelectedRawEventOriginKeys] = useState<
    Set<string>
  >(() => new Set());
  const [isMarkingSpam, setIsMarkingSpam] = useState(false);
  const [isRemovingSpamCorrection, setIsRemovingSpamCorrection] =
    useState(false);
  const [feedback, setFeedback] = useState<EventsActionFeedback | null>(null);
  const rawEventsByOriginKey = useMemo(() => {
    const items = new Map<string, RawEventCardData>();

    for (const columnsByDate of Object.values(eventsByDate)) {
      for (const columnItems of Object.values(columnsByDate)) {
        if (!columnItems) {
          continue;
        }

        for (const item of columnItems) {
          if (isRawEvent(item)) {
            items.set(eventOriginKey(item.eventOrigin), item);
          }
        }
      }
    }

    return items;
  }, [eventsByDate]);
  const selectedRawEvents = useMemo(
    () =>
      Array.from(selectedRawEventOriginKeys)
        .map((originKey) => rawEventsByOriginKey.get(originKey))
        .filter((item): item is RawEventCardData => item !== undefined),
    [rawEventsByOriginKey, selectedRawEventOriginKeys],
  );
  const isSpamMarkerChangePending = isMarkingSpam || isRemovingSpamCorrection;

  useEffect(() => {
    setSelectedRawEventOriginKeys((current) => {
      if (current.size === 0) {
        return current;
      }

      const next = new Set(
        Array.from(current).filter((originKey) =>
          rawEventsByOriginKey.has(originKey),
        ),
      );
      if (next.size === current.size) {
        return current;
      }
      return next;
    });
  }, [rawEventsByOriginKey]);

  const handleToggleRawEventSelection = useCallback(
    (eventOrigin: EventOrigin) => {
      const originKey = eventOriginKey(eventOrigin);
      setSelectedRawEventOriginKeys((current) => {
        const next = new Set(current);

        if (next.has(originKey)) {
          next.delete(originKey);
        } else {
          next.add(originKey);
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

    setSelectedRawEventOriginKeys(new Set());
    setFeedback({
      tone: "success",
      message:
        "Spam markers saved. Re-run the pipeline and reload the UI to refresh the lanes.",
    });
  }, [selectedRawEvents]);

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
        selectedRawEventCount={selectedRawEvents.length}
        isRemovingSpamCorrection={isRemovingSpamCorrection}
        isMarkingSpam={isMarkingSpam}
        feedback={feedback}
        onMarkSelectedAsSpam={handleMarkSelectedAsSpam}
      />
      <VirtualizedDateSections
        eventsByDate={eventsByDate}
        selectedRawEventOriginKeys={selectedRawEventOriginKeys}
        isSpamMarkerChangePending={isSpamMarkerChangePending}
        onToggleRawEventSelection={handleToggleRawEventSelection}
        onRemoveSpamCorrection={handleRemoveSpamCorrection}
      />
    </div>
  );
}
