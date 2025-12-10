import Container from "react-bootstrap/Container";

import { getLatestLedgerEvents } from "@/db/client";

export default async function Home() {
  const events = await getLatestLedgerEvents(10);

  return (
    <Container fluid className="py-4">
      <h1 className="mb-4">Latest ledger events</h1>
      <ul className="list-unstyled">
        {events.map((event) => (
          <li key={event.id} className="mb-4">
            <div className="fw-semibold">
              {event.eventType} &middot; {new Date(event.timestamp).toISOString()}
            </div>
            <div className="text-muted small">
              {event.originLocation} / {event.originExternalId} &middot; {event.ingestion}
            </div>
            <ul className="mt-2 ps-3">
              {event.ledgerLegs.map((leg) => (
                <li key={leg.id}>
                  <span className="fw-semibold">{leg.assetId}</span>{" "}
                  <span className="text-nowrap">{leg.quantity}</span>{" "}
                  <span className="text-muted">({leg.walletId})</span>
                  {leg.isFee ? <span className="text-danger ms-1">fee</span> : null}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </Container>
  );
}
