"use client";

import type { ChangeEvent, CSSProperties } from "react";

import {
  Card,
  CardBody,
  CardHeader,
  ListGroup,
  ListGroupItem,
} from "react-bootstrap";

import { clsx } from "clsx";
import styles from "./LedgerEventCard.module.css";
import { OriginIcon } from "@/components/OriginIcon";
import { OriginId } from "@/components/OriginId";
import { useAccountNames } from "@/contexts/AccountNamesContext";
import { useCorrectionHighlight } from "@/contexts/CorrectionHighlightContext";
import { getLedgerLegQuantityPresentation } from "@/lib/ledgerLegQuantity";
import type { CorrectedEventCardData, RawEventCardData } from "@/types/events";

type LedgerEventCardProps = {
  event: RawEventCardData | CorrectedEventCardData;
  isSelected?: boolean;
  onSelectionChange?: (isSelected: boolean) => void;
  selectionDisabled?: boolean;
};

export function LedgerEventCard({
  event,
  isSelected = false,
  onSelectionChange,
  selectionDisabled = false,
}: LedgerEventCardProps) {
  const { timestamp, eventOrigin, legs } = event;
  const { resolveAccountName } = useAccountNames();
  const { getSourceHighlight } = useCorrectionHighlight();
  const place = eventOrigin.location.toLowerCase();
  const originId = eventOrigin.externalId;
  const sourceHighlight = getSourceHighlight(eventOrigin);
  const timestampLabel = new Date(timestamp).toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const hasSelectionControl = onSelectionChange !== undefined;

  const handleSelectionChange = (event: ChangeEvent<HTMLInputElement>) => {
    onSelectionChange?.(event.target.checked);
  };

  const cardStyle = sourceHighlight
    ? ({
        "--source-highlight-accent": sourceHighlight.accentColor,
        "--source-highlight-surface": sourceHighlight.surfaceColor,
      } as CSSProperties)
    : undefined;

  return (
    <Card
      className={clsx(
        "shadow-sm",
        styles.card,
        sourceHighlight && styles.highlightedCard,
      )}
      style={cardStyle}
    >
      <CardHeader
        className={clsx(
          "d-flex flex-wrap align-items-center gap-2",
          sourceHighlight && styles.highlightedHeader,
        )}
      >
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
      <CardBody className={clsx(sourceHighlight && styles.highlightedSurface)}>
        <ListGroup variant="flush" className="border rounded">
          {legs.map((leg) => {
            const quantityPresentation = getLedgerLegQuantityPresentation(leg);

            return (
              <ListGroupItem
                key={leg.id}
                className={clsx(
                  "d-flex align-items-center gap-1",
                  styles.leg,
                  sourceHighlight && styles.highlightedSurface,
                )}
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
      </CardBody>
    </Card>
  );
}
