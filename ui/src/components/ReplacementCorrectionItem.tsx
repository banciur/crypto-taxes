"use client";

import { ListGroup, ListGroupItem } from "react-bootstrap";

import { clsx } from "clsx";
import { CorrectionItem } from "@/components/CorrectionItem";
import { CorrectionRemoveButton } from "@/components/CorrectionRemoveButton";
import { OriginId } from "@/components/OriginId";
import { useAccountNames } from "@/contexts/AccountNamesContext";
import { getLedgerLegQuantityPresentation } from "@/lib/ledgerLegQuantity";
import type { ReplacementCorrectionItemData } from "@/types/events";
import styles from "./EventCard.module.css";

type ReplacementCorrectionItemProps = {
  item: ReplacementCorrectionItemData;
  actionDisabled: boolean;
  onRemove: () => void;
};

export function ReplacementCorrectionItem({
  item,
  actionDisabled,
  onRemove,
}: ReplacementCorrectionItemProps) {
  const { id, timestamp, sources, legs } = item;
  const { resolveAccountName } = useAccountNames();
  const action = (
    <CorrectionRemoveButton
      label={`Remove replacement correction ${id}`}
      disabled={actionDisabled}
      onClick={onRemove}
    />
  );

  return (
    <CorrectionItem
      label="Replacement"
      labelVariant="secondary"
      timestamp={timestamp}
      action={action}
    >
      <div className="mb-3 d-flex flex-wrap align-items-center gap-2">
        <span className="text-muted small">Sources</span>
        {sources.map((source) => (
          <OriginId
            key={`${source.location}:${source.externalId}`}
            originId={source.externalId}
            place={source.location.toLowerCase()}
            className="small text-muted"
          />
        ))}
      </div>
      <ListGroup variant="flush" className="border rounded">
        {legs.map((leg) => {
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
    </CorrectionItem>
  );
}
