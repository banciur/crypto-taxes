"use client";

import { useMemo } from "react";

import { Col } from "react-bootstrap";

import { LaneItem } from "@/components/LaneItem";
import { orderColumnKeys } from "@/consts";
import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";
import { eventOriginKey } from "@/lib/eventOrigin";
import type { EventsByTimestamp } from "@/types/events";
import {
  selectableEventFromLaneItem,
  type SelectableEvent,
} from "@/components/Events/selectableEvents";

type EventDateSectionProps = {
  itemsByColumn: EventsByTimestamp[string];
  selectedEvents: ReadonlyMap<string, SelectableEvent>;
  isCorrectionChangePending: boolean;
  onToggleEventSelection: (event: SelectableEvent) => void;
  onRemoveSpamCorrection: (eventOrigin: SelectableEvent["eventOrigin"]) => void;
  onRemoveReplacementCorrection: (correctionId: string) => void;
};

export function EventDateSection({
  itemsByColumn,
  selectedEvents,
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
          {itemsByColumn[columnKey]?.map((item) => {
            const selectableEvent = selectableEventFromLaneItem(item);
            const isSelected =
              selectableEvent !== null &&
              selectedEvents.has(eventOriginKey(selectableEvent.eventOrigin));

            return (
              <LaneItem
                key={item.id}
                item={item}
                selectableEvent={selectableEvent}
                isSelected={isSelected}
                isCorrectionChangePending={isCorrectionChangePending}
                onToggleEventSelection={onToggleEventSelection}
                onRemoveSpamCorrection={onRemoveSpamCorrection}
                onRemoveReplacementCorrection={onRemoveReplacementCorrection}
              />
            );
          })}
        </Col>
      ))}
    </>
  );
}
