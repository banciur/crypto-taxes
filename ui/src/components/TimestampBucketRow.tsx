"use client";

import { useMemo } from "react";

import { Col } from "react-bootstrap";

import { LedgerCorrectionCard } from "@/components/LedgerCorrectionCard";
import { LedgerEventCard } from "@/components/LedgerEventCard";
import { orderColumnKeys } from "@/consts";
import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";
import type { EventOrigin, EventsByTimestamp } from "@/types/events";

type TimestampBucketRowProps = {
  itemsByColumn: EventsByTimestamp[string];
  selectedEventOriginKeys: ReadonlySet<string>;
  isCorrectionChangePending: boolean;
  onToggleEventSelection: (eventOrigin: EventOrigin) => void;
  onRemoveCorrection: (correctionId: string) => void;
};

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
          {itemsByColumn[columnKey]?.map((item) =>
            item.kind === "correction" ? (
              <LedgerCorrectionCard
                key={item.id}
                item={item}
                actionDisabled={isCorrectionChangePending}
                onRemove={() => onRemoveCorrection(item.id)}
              />
            ) : (
              <LedgerEventCard
                key={item.id}
                event={item}
                selectedEventOriginKeys={selectedEventOriginKeys}
                isCorrectionChangePending={isCorrectionChangePending}
                onToggleEventSelection={onToggleEventSelection}
              />
            ),
          )}
        </Col>
      ))}
    </>
  );
}
