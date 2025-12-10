"use client";
import { Badge, Card, ListGroup } from "react-bootstrap";

import type { LedgerEventWithLegs } from "@/db/client";
import { formatDateISO} from "@/lib/dateFormatter";

type LedgerEventProps = {
  event: LedgerEventWithLegs;
};

export function LedgerEvent({ event }: LedgerEventProps) {
  const timestampLabel = formatDateISO(new Date(event.timestamp));

  return (
    <Card className="shadow-sm h-100">
      <Card.Header className="d-flex flex-wrap align-items-center gap-2">
        <Badge bg="primary" className="text-uppercase">
          {event.eventType}
        </Badge>
        <span className="text-muted small">{timestampLabel}</span>
        <span className="ms-auto text-muted small">
          {event.originLocation}
        </span>
      </Card.Header>
      <Card.Body>
        <ListGroup variant="flush" className="border rounded">
          {event.ledgerLegs.map((leg) => (
            <ListGroup.Item
              key={leg.id}
              className="d-flex align-items-center gap-3"
            >
              <Badge bg={leg.isFee ? "danger" : "info"} className="text-uppercase">
                {leg.isFee ? "Fee" : "Leg"}
              </Badge>
              <div className="flex-grow-1">
                <div className="fw-semibold">{leg.assetId}</div>
                <div className="text-muted small">Wallet {leg.walletId}</div>
              </div>
              <div className="text-nowrap fw-semibold">{leg.quantity}</div>
            </ListGroup.Item>
          ))}
        </ListGroup>
      </Card.Body>
    </Card>
  );
}
