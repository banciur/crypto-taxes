"use client";

import { Badge, Card, ListGroup } from "react-bootstrap";

import { clsx } from "clsx";
import styles from "./EventCard.module.css";

export type EventLeg = {
  id: string;
  assetId: string;
  walletId: string;
  quantity: string;
  isFee: boolean;
};

type EventCardProps = {
  timestamp: string;
  eventType: string;
  place: string;
  legs: EventLeg[];
};

export function EventCard({
  timestamp,
  eventType,
  place,
  legs,
}: EventCardProps) {
  const timestampLabel = new Date(timestamp).toLocaleString("en-GB", {
    timeZone: "UTC",
  });
  const legQuantityClassName = (leg: EventLeg) => {
    if (leg.isFee) {
      return "text-info";
    }
    const quantityValue = Number(leg.quantity);
    if (quantityValue < 0) {
      return "text-danger";
    } else {
      return "text-success";
    }
  };

  return (
    <Card className="shadow-sm">
      <Card.Header className="d-flex flex-wrap align-items-center gap-2">
        <Badge className="text-uppercase">{eventType}</Badge>
        <span className="text-muted small">{timestampLabel}</span>
        <span className="ms-auto text-muted small">{place}</span>
      </Card.Header>
      <Card.Body>
        <ListGroup variant="flush" className="border rounded">
          {legs.map((leg) => (
            <ListGroup.Item
              key={leg.id}
              className={clsx("d-flex align-items-center gap-1", styles.leg)}
            >
              <span>{leg.assetId}</span>
              <span>{leg.walletId}</span>
              <span
                className={clsx("flex-shrink-0", legQuantityClassName(leg))}
              >
                {leg.quantity}
              </span>
            </ListGroup.Item>
          ))}
        </ListGroup>
      </Card.Body>
    </Card>
  );
}
