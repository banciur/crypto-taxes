"use client";

import { useMemo } from "react";

import { Col } from "react-bootstrap";

import { LaneItem } from "@/components/LaneItem";
import { orderColumnKeys } from "@/consts";
import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";
import { eventOriginKey } from "@/lib/eventOrigin";
import type {
  EventOrigin,
  EventsByTimestamp,
  LaneItemData,
} from "@/types/events";

type EventDateSectionProps = {
  itemsByColumn: EventsByTimestamp[string];
  selectedEventOriginKeys: ReadonlySet<string>;
  isSpamMarkerChangePending: boolean;
  onToggleEventSelection: (eventOrigin: EventOrigin) => void;
  onRemoveSpamCorrection: (eventOrigin: EventOrigin) => void;
};

const isSelectedRawEvent = (
  item: LaneItemData,
  selectedEventOriginKeys: ReadonlySet<string>,
) =>
  item.kind === "raw-event" &&
  selectedEventOriginKeys.has(eventOriginKey(item.eventOrigin));

export function EventDateSection({
  itemsByColumn,
  selectedEventOriginKeys,
  isSpamMarkerChangePending,
  onToggleEventSelection,
  onRemoveSpamCorrection,
}: EventDateSectionProps) {
  const { selected } = useUrlColumnSelection();
  const orderedSelectedColumns = useMemo(
    () => orderColumnKeys(selected),
    [selected],
  );

  return (
    <>
      {orderedSelectedColumns.map((columnKey) => (
        <Col
          xs={12 / orderedSelectedColumns.length}
          className="d-flex flex-column gap-2"
          key={`section-${columnKey}`}
        >
          {itemsByColumn[columnKey]?.map((item) => (
            <LaneItem
              key={item.id}
              item={item}
              isSelected={isSelectedRawEvent(item, selectedEventOriginKeys)}
              isSpamMarkerChangePending={isSpamMarkerChangePending}
              onToggleEventSelection={onToggleEventSelection}
              onRemoveSpamCorrection={onRemoveSpamCorrection}
            />
          ))}
        </Col>
      ))}
    </>
  );
}
