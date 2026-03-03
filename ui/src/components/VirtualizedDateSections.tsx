"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";

import { useVirtualizer } from "@tanstack/react-virtual";
import { clsx } from "clsx";

import { EventDateSection } from "@/components/EventDateSection";
import { useVisibleDay } from "@/contexts/VisibleDayContext";
import { dayIdFor } from "@/lib/dayHash";
import { dayKeyForTimestampBucket } from "@/lib/timestampBuckets";
import type { EventOrigin, EventsByTimestamp } from "@/types/events";
import { Col, Row } from "react-bootstrap";

type DayHeaderRow = {
  kind: "day-header";
  key: string;
  dayKey: string;
};

type EventBucketRow = {
  kind: "event-bucket";
  key: string;
  dayKey: string;
  itemsByColumn: EventsByTimestamp[string];
};

type TimelineRow = DayHeaderRow | EventBucketRow;

type VirtualizedDateSectionsProps = {
  eventsByTimestamp: EventsByTimestamp;
  selectedRawEventOriginKeys: ReadonlySet<string>;
  isSpamMarkerChangePending: boolean;
  className?: string;
  onToggleRawEventSelection: (eventOrigin: EventOrigin) => void;
  onRemoveSpamCorrection: (eventOrigin: EventOrigin) => void;
};

export function VirtualizedDateSections({
  eventsByTimestamp,
  selectedRawEventOriginKeys,
  isSpamMarkerChangePending,
  className,
  onToggleRawEventSelection,
  onRemoveSpamCorrection,
}: VirtualizedDateSectionsProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { activeDayKey, activeDaySource, setActiveDayKey } = useVisibleDay();
  const { rows, firstRowIndexByDay } = useMemo(() => {
    const nextRows: TimelineRow[] = [];
    const nextFirstRowIndexByDay = new Map<string, number>();
    let previousDayKey: string | null = null;
    const orderedTimestampBuckets = Object.keys(eventsByTimestamp).sort(
      (a, b) => Number(b) - Number(a),
    );

    for (const timestampBucket of orderedTimestampBuckets) {
      const itemsByColumn = eventsByTimestamp[timestampBucket];
      const dayKey = dayKeyForTimestampBucket(timestampBucket);

      if (dayKey !== previousDayKey) {
        nextFirstRowIndexByDay.set(dayKey, nextRows.length);
        nextRows.push({
          kind: "day-header",
          key: `day-${dayKey}`,
          dayKey,
        });
        previousDayKey = dayKey;
      }

      nextRows.push({
        kind: "event-bucket",
        key: `bucket-${timestampBucket}`,
        dayKey,
        itemsByColumn,
      });
    }

    return { rows: nextRows, firstRowIndexByDay: nextFirstRowIndexByDay };
  }, [eventsByTimestamp]);

  const updateVisibleDay = useCallback(
    (items: Array<{ start: number; end: number; index: number }>) => {
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

      const row = rows[visibleItem.index];
      if (!row) return;
      setActiveDayKey(row.dayKey, "scroll");
    },
    [rows, setActiveDayKey],
  );

  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: (index) => (rows[index]?.kind === "day-header" ? 28 : 110),
    gap: 16,
    overscan: 5,
    onChange: (instance, sync) => {
      if (sync) return;
      updateVisibleDay(instance.getVirtualItems());
    },
  });

  useEffect(() => {
    if (
      !activeDayKey ||
      activeDaySource === "scroll" ||
      !containerRef.current
    ) {
      return;
    }

    const index = firstRowIndexByDay.get(activeDayKey);
    if (index === undefined) return;
    virtualizer.scrollToIndex(index, { align: "start" });
  }, [activeDayKey, activeDaySource, firstRowIndexByDay, virtualizer]);

  const items = virtualizer.getVirtualItems();

  return (
    <div ref={containerRef} className={clsx("overflow-y-auto", className)}>
      <div
        className="w-100 position-relative"
        style={{
          height: `${virtualizer.getTotalSize()}px`,
        }}
      >
        {items.map((virtualRow) => {
          const row = rows[virtualRow.index];
          if (!row) {
            return null;
          }

          return (
            <Row
              key={row.key}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              className="w-100 position-absolute top-0 start-0"
              style={{
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              {row.kind === "day-header" ? (
                <Col id={dayIdFor(row.dayKey)} className="fw-semibold">
                  {row.dayKey}
                </Col>
              ) : (
                <EventDateSection
                  itemsByColumn={row.itemsByColumn}
                  selectedRawEventOriginKeys={selectedRawEventOriginKeys}
                  isSpamMarkerChangePending={isSpamMarkerChangePending}
                  onToggleRawEventSelection={onToggleRawEventSelection}
                  onRemoveSpamCorrection={onRemoveSpamCorrection}
                />
              )}
            </Row>
          );
        })}
      </div>
    </div>
  );
}
