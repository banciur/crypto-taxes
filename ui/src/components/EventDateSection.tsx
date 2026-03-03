"use client";

import { useMemo } from "react";

import { Col, Row } from "react-bootstrap";

import { LaneItem } from "@/components/LaneItem";
import { orderColumnKeys } from "@/consts";
import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";
import { eventOriginKey } from "@/lib/eventOrigin";
import type { EventOrigin, EventsByDate, LaneItemData } from "@/types/events";

type EventDateSectionProps = {
  dateKey: string;
  itemsByColumn: EventsByDate[string];
  selectedRawEventOriginKeys: ReadonlySet<string>;
  isSpamMarkerChangePending: boolean;
  onToggleRawEventSelection: (eventOrigin: EventOrigin) => void;
  onRemoveSpamCorrection: (eventOrigin: EventOrigin) => void;
};

const isSelectedRawEvent = (
  item: LaneItemData,
  selectedRawEventOriginKeys: ReadonlySet<string>,
) =>
  item.kind === "raw-event" &&
  selectedRawEventOriginKeys.has(eventOriginKey(item.eventOrigin));

export function EventDateSection({
  dateKey,
  itemsByColumn,
  selectedRawEventOriginKeys,
  isSpamMarkerChangePending,
  onToggleRawEventSelection,
  onRemoveSpamCorrection,
}: EventDateSectionProps) {
  const { selected } = useUrlColumnSelection();
  const orderedSelectedColumns = useMemo(
    () => orderColumnKeys(selected),
    [selected],
  );

  return (
    <>
      <h5>{dateKey}</h5>
      <Row>
        {orderedSelectedColumns.map((columnKey) => (
          <Col
            xs={12 / orderedSelectedColumns.length}
            className="d-flex flex-column gap-2"
            key={`section-${dateKey}-${columnKey}`}
          >
            {itemsByColumn[columnKey]?.map((item) => (
              <LaneItem
                key={item.id}
                item={item}
                isSelected={isSelectedRawEvent(
                  item,
                  selectedRawEventOriginKeys,
                )}
                isSpamMarkerChangePending={isSpamMarkerChangePending}
                onToggleRawEventSelection={onToggleRawEventSelection}
                onRemoveSpamCorrection={onRemoveSpamCorrection}
              />
            ))}
          </Col>
        ))}
      </Row>
    </>
  );
}
