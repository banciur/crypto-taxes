"use client";

import { ListGroup, ListGroupItem } from "react-bootstrap";

import { clsx } from "clsx";
import { CorrectionItem } from "@/components/CorrectionItem";
import { useAccountNames } from "@/contexts/AccountNamesContext";
import { getLedgerLegQuantityPresentation } from "@/lib/ledgerLegQuantity";
import type { SeedCorrectionItemData } from "@/types/events";
import styles from "./EventCard.module.css";

type SeedCorrectionItemProps = {
  item: SeedCorrectionItemData;
};

export function SeedCorrectionItem({ item }: SeedCorrectionItemProps) {
  const { timestamp, legs } = item;
  const { resolveAccountName } = useAccountNames();

  return (
    <CorrectionItem
      label="Seed event"
      labelVariant="secondary"
      timestamp={timestamp}
    >
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
