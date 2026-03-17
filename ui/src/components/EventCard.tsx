"use client";

import type { ChangeEvent } from "react";

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
import { useAccountNameResolver } from "@/contexts/AccountNamesContext";
import type {
  CorrectedEventCardData,
  LedgerLeg,
  RawEventCardData,
} from "@/types/events";

type EventCardProps = {
  event: RawEventCardData | CorrectedEventCardData;
  isSelected?: boolean;
  onSelectionChange?: (isSelected: boolean) => void;
  selectionDisabled?: boolean;
};

export function EventCard({
  event,
  isSelected = false,
  onSelectionChange,
  selectionDisabled = false,
}: EventCardProps) {
  const { timestamp, eventOrigin, legs } = event;
  const resolveAccountName = useAccountNameResolver();
  const place = eventOrigin.location.toLowerCase();
  const originId = eventOrigin.externalId;
  const timestampLabel = new Date(timestamp).toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const legQuantityClassName = (leg: LedgerLeg) => {
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
  const hasSelectionControl = onSelectionChange !== undefined;

  const handleSelectionChange = (event: ChangeEvent<HTMLInputElement>) => {
    onSelectionChange?.(event.target.checked);
  };

  return (
    <Card className="shadow-sm">
      <CardHeader className="d-flex flex-wrap align-items-center gap-2">
        {hasSelectionControl && (
          <input
            type="checkbox"
            className="form-check-input mt-0"
            checked={isSelected}
            disabled={selectionDisabled}
            onChange={handleSelectionChange}
            aria-label={`Select event ${originId}`}
          />
        )}
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
              <span title={leg.accountChainId}>
                {resolveAccountName(leg.accountChainId)}
              </span>
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
