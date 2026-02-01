"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";

import type { ColumnKey } from "@/consts";
import { orderColumnKeys } from "@/consts";

import { useVirtualizer } from "@tanstack/react-virtual";
import { EventCard } from "@/components/EventCard";
import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";
import { Col, Row } from "react-bootstrap";

type EventsByDate = Record<string, Partial<Record<ColumnKey, object[]>>>;

type EventsProps = {
  eventsByDate: EventsByDate;
};

const dateKeyFromHash = (hash: string) => {
  if (!hash.startsWith("#day-")) return null;
  const key = hash.slice("#day-".length);
  return key.length > 0 ? key : null;
};

export function Events({ eventsByDate }: EventsProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const lastHashRef = useRef<string | null>(null);
  const { selected } = useUrlColumnSelection();

  const dates = useMemo(() => Object.keys(eventsByDate), [eventsByDate]);
  const orderedSelectedColumns = useMemo(
    () => orderColumnKeys(selected),
    [selected],
  );

  const virtualizer = useVirtualizer({
    count: dates.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 110,
    gap: 16,
    overscan: 5,
    onChange: (instance, sync) => {
      if (!sync) return;
      updateHash(instance.getVirtualItems());
    },
  });

  const updateHash = useCallback(
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

      const nextHash = `#day-${dateKey}`;
      if (lastHashRef.current === nextHash) return;
      lastHashRef.current = nextHash;

      const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
      history.replaceState(null, "", nextUrl);
    },
    [dates, virtualizer],
  );

  const scrollToDate = useCallback(
    (dateKey: string) => {
      if (!containerRef.current) return;
      const index = dates.findIndex((element) => element === dateKey);
      if (index === -1) return;
      virtualizer.scrollToIndex(index, { align: "start" });
    },
    [dates, virtualizer],
  );

  useEffect(() => {
    const handleHashChange = () => {
      const dateKey = dateKeyFromHash(window.location.hash);
      if (!dateKey) return;
      lastHashRef.current = window.location.hash;
      scrollToDate(dateKey);
    };

    handleHashChange();
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, [scrollToDate]);

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
              id={`day-${dateKey}`}
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
