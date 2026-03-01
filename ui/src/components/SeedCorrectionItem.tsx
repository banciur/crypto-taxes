"use client";

import { ListGroup, ListGroupItem } from "react-bootstrap";

import { clsx } from "clsx";
import { CorrectionItem } from "@/components/CorrectionItem";
import type { EventLeg } from "@/types/events";
import styles from "./EventCard.module.css";

type SeedCorrectionItemProps = {
  timestamp: string;
  legs: EventLeg[];
};

const legQuantityClassName = (leg: EventLeg) => {
  if (leg.isFee) {
    return "text-info";
  }
  const quantityValue = Number(leg.quantity);
  if (quantityValue < 0) {
    return "text-danger";
  }
  return "text-success";
};

export function SeedCorrectionItem({
  timestamp,
  legs,
}: SeedCorrectionItemProps) {
  return (
    <CorrectionItem
      label="Seed event"
      labelVariant="secondary"
      timestamp={timestamp}
    >
      <ListGroup variant="flush" className="border rounded">
        {legs.map((leg) => (
          <ListGroupItem
            key={leg.id}
            className={clsx("d-flex align-items-center gap-1", styles.leg)}
          >
            <span>{leg.assetId}</span>
            <span title={leg.accountChainId}>{leg.accountName}</span>
            <span className={clsx("flex-shrink-0", legQuantityClassName(leg))}>
              {leg.quantity}
            </span>
          </ListGroupItem>
        ))}
      </ListGroup>
    </CorrectionItem>
  );
}
