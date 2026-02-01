"use client";

import { useMemo, useRef } from "react";

import type { ColumnKey } from "@/consts";
import { orderColumnKeys } from "@/consts";

import { useVirtualizer } from "@tanstack/react-virtual";
import { EventCard } from "@/components/EventCard";
import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";

type EventsByDate = Record<string, Partial<Record<ColumnKey, object[]>>>;

type EventsProps = {
  eventsByDate: EventsByDate;
};

export function Events({ eventsByDate }: EventsProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { selected } = useUrlColumnSelection();

  const dates = useMemo(() => Object.keys(eventsByDate), [eventsByDate]);
  const orderedSelectedColumns = useMemo(
    () => orderColumnKeys(selected),
    [selected],
  );
  const columnSpan = 12 / orderedSelectedColumns.length;

  const virtualizer = useVirtualizer({
    count: dates.length,
    getScrollElement: () => containerRef.current,
    estimateSize: (_index) => 110,
    overscan: 5,
  });

  const items = virtualizer.getVirtualItems();

  return (
    <div
      ref={containerRef}
      style={{
        height: "100%",
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
            <div
              key={virtualRow.index}
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
              <h5>{dateKey}</h5>
              <div className="row">
                {orderedSelectedColumns.map((columnKey) => (
                  <div
                    className={`col-${columnSpan}`}
                    key={`row-${virtualRow.index}-${columnKey}`}
                  >
                    {eventsByDate[dateKey][columnKey]?.map((event) => (
                      <EventCard key={event.id} {...event} />
                    ))}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
