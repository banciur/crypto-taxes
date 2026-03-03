"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";

import { useVirtualizer } from "@tanstack/react-virtual";
import { clsx } from "clsx";
import { Col, Row } from "react-bootstrap";

import { EventDateSection } from "@/components/EventDateSection";
import { useVisibleDay } from "@/contexts/VisibleDayContext";
import { dayIdFor } from "@/lib/dayHash";
import type { EventOrigin, EventsByDate } from "@/types/events";

type VirtualizedDateSectionsProps = {
  eventsByDate: EventsByDate;
  selectedRawEventOriginKeys: ReadonlySet<string>;
  isSpamMarkerChangePending: boolean;
  className?: string;
  onToggleRawEventSelection: (eventOrigin: EventOrigin) => void;
  onRemoveSpamCorrection: (eventOrigin: EventOrigin) => void;
};

export function VirtualizedDateSections({
  eventsByDate,
  selectedRawEventOriginKeys,
  isSpamMarkerChangePending,
  className,
  onToggleRawEventSelection,
  onRemoveSpamCorrection,
}: VirtualizedDateSectionsProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { activeDayKey, activeDaySource, setActiveDayKey } = useVisibleDay();
  const dates = useMemo(() => Object.keys(eventsByDate), [eventsByDate]);

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

      const dateKey = dates[visibleItem.index];
      if (!dateKey) return;
      setActiveDayKey(dateKey, "scroll");
    },
    [dates, setActiveDayKey],
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
    <div ref={containerRef} className={clsx("overflow-y-auto", className)}>
      <div
        className="w-100 position-relative"
        style={{
          height: `${virtualizer.getTotalSize()}px`,
        }}
      >
        {items.map((virtualRow) => {
          const dateKey = dates[virtualRow.index];
          if (!dateKey) {
            return null;
          }

          return (
            <Row
              key={dateKey}
              id={dayIdFor(dateKey)}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              className="w-100 position-absolute top-0 start-0"
              style={{
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <Col>
                <EventDateSection
                  dateKey={dateKey}
                  itemsByColumn={eventsByDate[dateKey]}
                  selectedRawEventOriginKeys={selectedRawEventOriginKeys}
                  isSpamMarkerChangePending={isSpamMarkerChangePending}
                  onToggleRawEventSelection={onToggleRawEventSelection}
                  onRemoveSpamCorrection={onRemoveSpamCorrection}
                />
              </Col>
            </Row>
          );
        })}
      </div>
    </div>
  );
}
