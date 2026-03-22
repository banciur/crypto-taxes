"use client";

import type { CSSProperties } from "react";

import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  ListGroup,
  ListGroupItem,
} from "react-bootstrap";

import { clsx } from "clsx";
import { CorrectionRemoveButton } from "@/components/CorrectionRemoveButton";
import { OriginId } from "@/components/OriginId";
import { useAccountNames } from "@/contexts/AccountNamesContext";
import { useCorrectionHighlight } from "@/contexts/CorrectionHighlightContext";
import { getLedgerLegQuantityPresentation } from "@/lib/ledgerLegQuantity";
import type { CorrectionItemData } from "@/types/events";
import styles from "./LedgerCorrectionCard.module.css";

type LedgerCorrectionCardProps = {
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

export function LedgerCorrectionCard({
  item,
  actionDisabled,
  onRemove,
}: LedgerCorrectionCardProps) {
  const { resolveAccountName } = useAccountNames();
  const { clearHighlightedSources, getSourceHighlight, setHighlightedSources } =
    useCorrectionHighlight();
  const label = correctionLabel(item);
  const labelVariant = correctionLabelVariant(item);

  const timestampLabel = new Date(item.timestamp).toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const hasSources = item.sources.length > 0;
  const handleMouseEnter = hasSources
    ? () => setHighlightedSources(item.sources)
    : undefined;
  const handleMouseLeave = hasSources ? clearHighlightedSources : undefined;

  return (
    <Card
      className="shadow-sm"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <CardHeader className="d-flex flex-wrap align-items-center gap-2">
        <Badge
          bg={labelVariant}
          className={labelVariant === "warning" ? "text-dark" : undefined}
        >
          {label}
        </Badge>
        <span className="text-muted small">{timestampLabel}</span>
        <CorrectionRemoveButton
          label={`Remove correction ${item.id}`}
          disabled={actionDisabled}
          onClick={onRemove}
          className="ms-auto"
        />
      </CardHeader>
      <CardBody>
        {hasSources && (
          <div className="mb-3 d-flex flex-wrap align-items-center gap-2">
            <span className="text-muted small">Sources</span>
            {item.sources.map((source) => {
              const sourceHighlight = getSourceHighlight(source);
              const sourceStyle = sourceHighlight
                ? ({
                    "--source-highlight-accent": sourceHighlight.accentColor,
                    "--source-highlight-surface": sourceHighlight.surfaceColor,
                  } as CSSProperties)
                : undefined;

              return (
                <OriginId
                  key={`${source.location}:${source.externalId}`}
                  originId={source.externalId}
                  place={source.location.toLowerCase()}
                  className={clsx(
                    "small",
                    sourceHighlight ? styles.highlightedSource : "text-muted",
                  )}
                  style={sourceStyle}
                />
              );
            })}
          </div>
        )}

        {item.legs.length > 0 && (
          <ListGroup variant="flush" className="border rounded">
            {item.legs.map((leg) => {
              const quantityPresentation =
                getLedgerLegQuantityPresentation(leg);

              return (
                <ListGroupItem
                  key={leg.id}
                  className={clsx(
                    "d-flex align-items-center gap-1",
                    styles.leg,
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
        )}

        {item.sources.length === 0 && item.pricePerToken !== undefined && (
          <div className="mt-3 small text-muted">
            Price per token: {item.pricePerToken}
          </div>
        )}

        {item.note?.trim() && (
          <div className="mt-3 small text-muted">{item.note}</div>
        )}
      </CardBody>
    </Card>
  );
}
