"use client";

import { Badge, Card, ListGroup } from "react-bootstrap";

import type { SeedEventWithLegs } from "@/db/client";

type SeedEventProps = {
  event: SeedEventWithLegs;
};

export function SeedEvent({ event }: SeedEventProps) {
  const timestampLabel = new Date(event.timestamp).toLocaleString("en-GB", {
    timeZone: "UTC",
  });

  return (
    <Card className="shadow-sm">
      <Card.Header className="d-flex flex-wrap align-items-center gap-2">
        <Badge bg="success" className="text-uppercase">
          seed
        </Badge>
        <span className="text-muted small">{timestampLabel}</span>
        <span className="ms-auto text-muted small">
          price/token {event.pricePerToken}
        </span>
      </Card.Header>
      <Card.Body>
        <ListGroup variant="flush" className="border rounded">
          {event.seedEventLegs.map((leg) => (
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
