"use client";

import { Badge, Card, ListGroup } from "react-bootstrap";

import type { CorrectedLedgerEventWithLegs } from "@/db/client";

type CorrectedEventProps = {
  event: CorrectedLedgerEventWithLegs;
};

export function CorrectedEvent({ event }: CorrectedEventProps) {
  const timestampLabel = new Date(event.timestamp).toLocaleString("en-GB", {
    timeZone: "UTC",
  });

  return (
    <Card className="shadow-sm">
      <Card.Header className="d-flex flex-wrap align-items-center gap-2">
        <Badge bg="warning" className="text-uppercase">
          {event.eventType}
        </Badge>
        <span className="text-muted small">{timestampLabel}</span>
        <span className="ms-auto text-muted small">{event.originLocation}</span>
      </Card.Header>
      <Card.Body>
        <ListGroup variant="flush" className="border rounded">
          {event.correctedLedgerLegs.map((leg) => (
            <ListGroup.Item
              key={leg.id}
              className="d-flex align-items-center gap-2"
            >
              <Badge
                bg={leg.isFee ? "danger" : "info"}
                className="text-uppercase"
              >
                {leg.isFee ? "fee" : "leg"}
              </Badge>
              <span>{leg.assetId}</span>
              <span>{leg.walletId}</span>
              <span>{leg.quantity}</span>
            </ListGroup.Item>
          ))}
        </ListGroup>
      </Card.Body>
    </Card>
  );
}
