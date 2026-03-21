"use client";

import { ListGroup, ListGroupItem } from "react-bootstrap";

import { clsx } from "clsx";
import { CorrectionItem } from "@/components/CorrectionItem";
import { CorrectionRemoveButton } from "@/components/CorrectionRemoveButton";
import { OriginId } from "@/components/OriginId";
import { useAccountNames } from "@/contexts/AccountNamesContext";
import { getLedgerLegQuantityPresentation } from "@/lib/ledgerLegQuantity";
import type { CorrectionItemData } from "@/types/events";
import styles from "./EventCard.module.css";

type LedgerCorrectionItemProps = {
  item: CorrectionItemData;
  actionDisabled: boolean;
  onRemove: () => void;
};

const correctionLabel = (item: CorrectionItemData) => {
  if (item.sources.length === 0) {
    return "Opening balance";
  }
  if (item.legs.length === 0) {
    return "Discard";
  }
  return "Replacement";
};

const correctionLabelVariant = (item: CorrectionItemData) =>
  item.legs.length === 0 && item.sources.length > 0 ? "warning" : "secondary";

export function LedgerCorrectionItem({
  item,
  actionDisabled,
  onRemove,
}: LedgerCorrectionItemProps) {
  const { resolveAccountName } = useAccountNames();
  const action = (
    <CorrectionRemoveButton
      label={`Remove correction ${item.id}`}
      disabled={actionDisabled}
      onClick={onRemove}
    />
  );

  return (
    <CorrectionItem
      label={correctionLabel(item)}
      labelVariant={correctionLabelVariant(item)}
      timestamp={item.timestamp}
      action={action}
    >
      {item.sources.length > 0 && (
        <div className="mb-3 d-flex flex-wrap align-items-center gap-2">
          <span className="text-muted small">Sources</span>
          {item.sources.map((source) => (
            <OriginId
              key={`${source.location}:${source.externalId}`}
              originId={source.externalId}
              place={source.location.toLowerCase()}
              className="small text-muted"
            />
          ))}
        </div>
      )}

      {item.legs.length > 0 && (
        <ListGroup variant="flush" className="border rounded">
          {item.legs.map((leg) => {
            const quantityPresentation = getLedgerLegQuantityPresentation(leg);

            return (
              <ListGroupItem
                key={leg.id}
                className={clsx("d-flex align-items-center gap-1", styles.leg)}
              >
                <span>{leg.assetId}</span>
                <span title={leg.accountChainId}>
                  {resolveAccountName(leg.accountChainId)}
                </span>
                <span
                  className={clsx(
                    "flex-shrink-0",
                    quantityPresentation.className,
                  )}
                >
                  {quantityPresentation.text}
                </span>
              </ListGroupItem>
            );
          })}
        </ListGroup>
      )}

      {item.sources.length === 0 && item.pricePerToken !== null && (
        <div className="mt-3 small text-muted">
          Price per token: {item.pricePerToken}
        </div>
      )}

      {item.note?.trim() && (
        <div className="mt-3 small text-muted">{item.note}</div>
      )}
    </CorrectionItem>
  );
}
