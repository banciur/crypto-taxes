"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";

import type { ColumnKey } from "@/consts";
import { orderColumnKeys } from "@/consts";

import { useVirtualizer } from "@tanstack/react-virtual";
import { EventCard } from "@/components/EventCard";
import { useVisibleDay } from "@/contexts/VisibleDayContext";
import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";
import { dayIdFor } from "@/lib/dayHash";
import type { EventCardData } from "@/types/events";
import { Col, Row } from "react-bootstrap";

type EventsByDate = Record<string, Partial<Record<ColumnKey, EventCardData[]>>>;

type EventsProps = {
  eventsByDate: EventsByDate;
};

export function Events({ eventsByDate }: EventsProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { selected } = useUrlColumnSelection();
  const { activeDayKey, activeDaySource, setActiveDayKey } = useVisibleDay();

  const dates = useMemo(() => Object.keys(eventsByDate), [eventsByDate]);
  const orderedSelectedColumns = useMemo(
    () => orderColumnKeys(selected),
    [selected],
  );

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
                      {eventsByDate[dateKey][columnKey]?.map((event) => (
                        <EventCard key={event.id} {...event} />
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
  );
}
