import { Col, Container, Row } from "react-bootstrap";

import { LedgerEvent } from "@/components/LedgerEvent";
import { getLatestLedgerEvents } from "@/db/client";

export default async function Home() {
  const events = await getLatestLedgerEvents();

  return (
    <Container fluid>
      <h1 className="mb-4">Latest ledger events</h1>
        {events.map((event) => (
        <Row className="g-3" key={event.id}>
          <Col>
            <LedgerEvent event={event} />
          </Col>
        </Row>
        ))}
    </Container>
  );
}
