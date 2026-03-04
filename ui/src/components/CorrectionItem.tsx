"use client";

import type { ReactNode } from "react";

import { Badge, Card, CardBody, CardHeader } from "react-bootstrap";

type CorrectionItemProps = {
  label: string;
  labelVariant: "secondary" | "warning";
  timestamp: string;
  action?: ReactNode;
  children: ReactNode;
};

export function CorrectionItem({
  label,
  labelVariant,
  timestamp,
  action,
  children,
}: CorrectionItemProps) {
  const timestampLabel = new Date(timestamp).toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <Card className="shadow-sm">
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
