"use client";

import { useMemo } from "react";

import { Col } from "react-bootstrap";

import { LedgerCorrectionCard } from "@/components/LedgerCorrectionCard";
import { LedgerEventCard } from "@/components/LedgerEventCard";
import { isSelectableEventItem } from "@/components/Events/selectableEvents";
import { orderColumnKeys } from "@/consts";
import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";
import { eventOriginKey } from "@/lib/eventOrigin";
import type {
  EventOrigin,
  EventsByTimestamp,
  LaneItemData,
} from "@/types/events";

type TimestampBucketRowProps = {
  itemsByColumn: EventsByTimestamp[string];
  selectedEventOriginKeys: ReadonlySet<string>;
  isCorrectionChangePending: boolean;
  onToggleEventSelection: (eventOrigin: EventOrigin) => void;
  onRemoveCorrection: (correctionId: string) => void;
};

const isSelectedEvent = (
  item: LaneItemData,
  selectedEventOriginKeys: ReadonlySet<string>,
) =>
  isSelectableEventItem(item) &&
  selectedEventOriginKeys.has(eventOriginKey(item.eventOrigin));

export function TimestampBucketRow({
  itemsByColumn,
  selectedEventOriginKeys,
  isCorrectionChangePending,
  onToggleEventSelection,
  onRemoveCorrection,
}: TimestampBucketRowProps) {
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
            if (item.kind === "correction") {
              return (
                <LedgerCorrectionCard
                  key={item.id}
                  item={item}
                  actionDisabled={isCorrectionChangePending}
                  onRemove={() => onRemoveCorrection(item.id)}
                />
              );
            }

            const isSelectable = isSelectableEventItem(item);

            return (
              <LedgerEventCard
                key={item.id}
                event={item}
                isSelected={isSelectedEvent(item, selectedEventOriginKeys)}
                selectionDisabled={isSelectable && isCorrectionChangePending}
                onSelectionChange={
                  isSelectable
                    ? () => onToggleEventSelection(item.eventOrigin)
                    : undefined
                }
              />
            );
          })}
        </Col>
      ))}
    </>
  );
}
