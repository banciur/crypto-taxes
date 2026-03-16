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
  isCorrectionChangePending: boolean;
  onToggleEventSelection: (eventOrigin: EventOrigin) => void;
  onRemoveSpamCorrection: (eventOrigin: EventOrigin) => void;
  onRemoveReplacementCorrection: (correctionId: string) => void;
};

const isSelectedEvent = (
  item: LaneItemData,
  selectedEventOriginKeys: ReadonlySet<string>,
) =>
  (item.kind === "raw-event" || item.kind === "corrected-event") &&
  selectedEventOriginKeys.has(eventOriginKey(item.eventOrigin));

export function EventDateSection({
  itemsByColumn,
  selectedEventOriginKeys,
  isCorrectionChangePending,
  onToggleEventSelection,
  onRemoveSpamCorrection,
  onRemoveReplacementCorrection,
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
              isSelected={isSelectedEvent(item, selectedEventOriginKeys)}
              isCorrectionChangePending={isCorrectionChangePending}
              onToggleEventSelection={onToggleEventSelection}
              onRemoveSpamCorrection={onRemoveSpamCorrection}
              onRemoveReplacementCorrection={onRemoveReplacementCorrection}
            />
          ))}
        </Col>
      ))}
    </>
  );
}
