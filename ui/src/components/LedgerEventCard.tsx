"use client";

import type { CSSProperties } from "react";

import { Badge, Button, Card, CardBody, CardHeader } from "react-bootstrap";

import { clsx } from "clsx";
import styles from "./LedgerEventCard.module.css";
import { isSelectableEventItem } from "@/components/Events/selectableEvents";
import { BASE_CURRENCY_ASSET_ID } from "@/consts";
import { LedgerLegList } from "@/components/LedgerLegList";
import { OriginIcon } from "@/components/OriginIcon";
import { OriginId } from "@/components/OriginId";
import { RemoveButton } from "@/components/RemoveButton";
import { useCorrectionHighlight } from "@/contexts/CorrectionHighlightContext";
import { usePriceOverrides } from "@/contexts/PriceOverridesContext";
import { formatDecimalString } from "@/lib/decimalStrings";
import { eventOriginKey } from "@/lib/eventOrigin";
import type {
  CorrectedEventCardData,
  EventOrigin,
  LedgerLeg,
  PriceOverrideEditorContext,
  RawEventCardData,
} from "@/types/events";

type LedgerEventCardProps = {
  event: RawEventCardData | CorrectedEventCardData;
  selectedEventOriginKeys?: ReadonlySet<string>;
  isCorrectionChangePending?: boolean;
  isPriceOverrideChangePending?: boolean;
  onToggleEventSelection?: (eventOrigin: EventOrigin) => void;
  onEditPriceOverride?: (context: PriceOverrideEditorContext) => void;
  onRemovePriceOverride?: (priceOverrideId: string) => void;
};

export function LedgerEventCard({
  event,
  selectedEventOriginKeys,
  isCorrectionChangePending = false,
  isPriceOverrideChangePending = false,
  onToggleEventSelection,
  onEditPriceOverride,
  onRemovePriceOverride,
}: LedgerEventCardProps) {
  const { timestamp, eventOrigin, note, legs } = event;
  const { getSourceHighlight } = useCorrectionHighlight();
  const { findPriceOverride } = usePriceOverrides();
  const place = eventOrigin.location.toLowerCase();
  const originId = eventOrigin.externalId;
  const sourceHighlight = getSourceHighlight(eventOrigin);
  const isSelectable = isSelectableEventItem(event);
  const isSelected =
    isSelectable &&
    selectedEventOriginKeys?.has(eventOriginKey(eventOrigin)) === true;
  const selectionDisabled = isSelectable && isCorrectionChangePending;
  const timestampLabel = new Date(timestamp).toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const hasSelectionControl =
    isSelectable && onToggleEventSelection !== undefined;

  const handleSelectionChange = () => {
    onToggleEventSelection?.(eventOrigin);
  };

  // Overrides price corrected events. A passthrough event keeps its raw origin in both lanes, so
  // this stays gated on the card kind to keep the affordance out of the raw lane.
  const showsPriceOverrides =
    event.kind === "corrected-event" && onEditPriceOverride !== undefined;

  const renderPriceOverride = (leg: LedgerLeg) => {
    const priceOverride = findPriceOverride(eventOrigin, leg.assetId);

    if (!priceOverride) {
      return (
        <Button
          type="button"
          size="sm"
          variant="outline-secondary"
          className="ms-auto py-0"
          disabled={isPriceOverrideChangePending}
          onClick={() =>
            onEditPriceOverride?.({
              eventOrigin,
              assetId: leg.assetId,
              legQuantity: leg.quantity,
            })
          }
        >
          Set price
        </Button>
      );
    }

    return (
      <span className="ms-auto d-flex align-items-center gap-1">
        <Badge bg="secondary" title={priceOverride.note}>
          {`${formatDecimalString(priceOverride.rateEur)} ${BASE_CURRENCY_ASSET_ID}/unit`}
        </Badge>
        <RemoveButton
          label={`Remove price override for ${leg.assetId}`}
          disabled={isPriceOverrideChangePending}
          onClick={() => onRemovePriceOverride?.(priceOverride.id)}
        />
      </span>
    );
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
      <CardBody className={sourceHighlight && styles.highlightedSurface}>
        <LedgerLegList
          legs={legs}
          itemClassName={sourceHighlight && styles.highlightedSurface}
          renderLegAccessory={
            showsPriceOverrides ? renderPriceOverride : undefined
          }
        />
        {note?.trim() && <div className="mt-3 small text-muted">{note}</div>}
      </CardBody>
    </Card>
  );
}
