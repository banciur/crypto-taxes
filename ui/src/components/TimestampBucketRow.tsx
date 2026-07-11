"use client";

import { useMemo } from "react";

import { Col } from "react-bootstrap";

import { AcquisitionDisposalCard } from "@/components/AcquisitionDisposalCard";
import { LedgerCorrectionCard } from "@/components/LedgerCorrectionCard";
import { LedgerEventCard } from "@/components/LedgerEventCard";
import { orderColumnKeys } from "@/consts";
import { useUrlColumnSelection } from "@/contexts/UrlColumnSelectionContext";
import type {
  EventOrigin,
  EventsByTimestamp,
  PriceOverrideEditorContext,
} from "@/types/events";

type TimestampBucketRowProps = {
  itemsByColumn: EventsByTimestamp[string];
  selectedEventOriginKeys: ReadonlySet<string>;
  isCorrectionChangePending: boolean;
  isPriceOverrideChangePending: boolean;
  onToggleEventSelection: (eventOrigin: EventOrigin) => void;
  onRemoveCorrection: (correctionId: string) => void;
  onEditPriceOverride: (context: PriceOverrideEditorContext) => void;
  onRemovePriceOverride: (priceOverrideId: string) => void;
};

function assertUnreachableLaneItem(item: never): never {
  throw new Error(
    `Unhandled lane item kind: ${(item as { kind: string }).kind}`,
  );
}

export function TimestampBucketRow({
  itemsByColumn,
  selectedEventOriginKeys,
  isCorrectionChangePending,
  isPriceOverrideChangePending,
  onToggleEventSelection,
  onRemoveCorrection,
  onEditPriceOverride,
  onRemovePriceOverride,
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
            switch (item.kind) {
              case "correction":
                return (
                  <LedgerCorrectionCard
                    key={item.id}
                    item={item}
                    actionDisabled={isCorrectionChangePending}
                    onRemove={() => onRemoveCorrection(item.id)}
                  />
                );
              case "ACQUISITION":
              case "DISPOSAL":
                return <AcquisitionDisposalCard key={item.id} item={item} />;
              case "raw-event":
              case "corrected-event":
                return (
                  <LedgerEventCard
                    key={item.id}
                    event={item}
                    selectedEventOriginKeys={selectedEventOriginKeys}
                    isCorrectionChangePending={isCorrectionChangePending}
                    isPriceOverrideChangePending={isPriceOverrideChangePending}
                    onToggleEventSelection={onToggleEventSelection}
                    onEditPriceOverride={onEditPriceOverride}
                    onRemovePriceOverride={onRemovePriceOverride}
                  />
                );
              default:
                return assertUnreachableLaneItem(item);
            }
          })}
        </Col>
      ))}
    </>
  );
}
