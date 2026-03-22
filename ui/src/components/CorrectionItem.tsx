"use client";

import type { ReactNode } from "react";

import { clsx } from "clsx";
import { Badge, Card, CardBody, CardHeader } from "react-bootstrap";

import { useCorrectionHighlight } from "@/contexts/CorrectionHighlightContext";
import type { EventOrigin } from "@/types/events";

type CorrectionItemProps = {
  label: string;
  labelVariant: "secondary" | "warning";
  timestamp: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  highlightSources?: EventOrigin[];
};

export function CorrectionItem({
  label,
  labelVariant,
  timestamp,
  action,
  children,
  className,
  highlightSources,
}: CorrectionItemProps) {
  const { setHighlightedSources, clearHighlightedSources } =
    useCorrectionHighlight();
  const timestampLabel = new Date(timestamp).toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const handleMouseEnter =
    highlightSources && highlightSources.length > 0
      ? () => setHighlightedSources(highlightSources)
      : undefined;
  const handleMouseLeave =
    highlightSources && highlightSources.length > 0
      ? clearHighlightedSources
      : undefined;

  return (
    <Card
      className={clsx("shadow-sm", className)}
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
        {action ? <div className="ms-auto">{action}</div> : null}
      </CardHeader>
      <CardBody>{children}</CardBody>
    </Card>
  );
}
