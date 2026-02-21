"use client";

import {
  Card,
  CardBody,
  CardHeader,
  ListGroup,
  ListGroupItem,
} from "react-bootstrap";

import { clsx } from "clsx";
import styles from "./EventCard.module.css";
import { OriginIcon } from "@/components/OriginIcon";
import { OriginId } from "@/components/OriginId";
import type { EventCardProps, EventLeg } from "@/types/events";

export function EventCard({
  timestamp,
  place,
  originId,
  legs,
}: EventCardProps) {
  const timestampLabel = new Date(timestamp).toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
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
      <CardHeader className="d-flex flex-wrap align-items-center gap-2">
        {originId && (
          <OriginId
            originId={originId}
            place={place}
            className="text-muted small"
          />
        )}
        <span className="text-muted small">{timestampLabel}</span>
        <OriginIcon place={place} className="ms-auto flex-shrink-0" />
      </CardHeader>
      <CardBody>
        <ListGroup variant="flush" className="border rounded">
          {legs.map((leg) => (
            <ListGroupItem
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
            </ListGroupItem>
          ))}
        </ListGroup>
      </CardBody>
    </Card>
  );
}
