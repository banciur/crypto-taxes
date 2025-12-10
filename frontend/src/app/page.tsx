import { Col, Container, Row } from "react-bootstrap";

import { DateChooser } from "@/components/DateChooser";
import { LedgerEvent } from "@/components/LedgerEvent";
import type { LedgerEventWithLegs } from "@/db/client";
import { getLatestLedgerEvents } from "@/db/client";
import { formatDateISO } from "@/lib/dateFormatter";

export default async function Home() {
  const events = await getLatestLedgerEvents();

  const grouped = events.reduce<{
    order: string[];
    eventsByDate: Record<string, LedgerEventWithLegs[]>;
  }>(
    (acc, event) => {
      const dateKey = new Date(event.timestamp).toISOString().slice(0, 10);
      if (!acc.eventsByDate[dateKey]) {
        acc.eventsByDate[dateKey] = [];
        acc.order.push(dateKey);
      }
      acc.eventsByDate[dateKey].push(event);
      return acc;
    },
    { order: [], eventsByDate: {} },
  );

  const dateSections = grouped.order.map((dateKey) => ({
    key: dateKey,
    count: grouped.eventsByDate[dateKey].length,
  }));

  return (
    <Container fluid>
      <h1>Ledger events</h1>
      <Row>
        <Col
          md={3}
          lg={2}
          className="overflow-auto"
          style={{ maxHeight: "calc(100vh - 56px)", scrollBehavior: "smooth" }}
        >
          <DateChooser dates={dateSections} />
        </Col>
        <Col
          md={9}
          lg={10}
          className="overflow-auto d-flex flex-column gap-5"
          style={{ maxHeight: "calc(100vh - 56px)", scrollBehavior: "smooth" }}
        >
          {grouped.order.map((dateKey) => {
            const dateEvents = grouped.eventsByDate[dateKey];
            const label = formatDateISO(
              new Date(`${dateKey}T00:00:00Z`),
            );
            return (
              <section
                id={`day-${dateKey}`}
                key={dateKey}
                className="d-flex flex-column gap-3"
              >
                <div className="d-flex align-items-baseline gap-3">
                  <h2 className="h4 mb-0">{label}</h2>
                  <span className="text-muted small">
                    {dateEvents.length} events
                  </span>
                </div>
                <div className="d-flex flex-column gap-3">
                  {dateEvents.map((event) => (
                    <LedgerEvent event={event} key={event.id} />
                  ))}
                </div>
              </section>
            );
          })}
        </Col>
      </Row>
    </Container>
  );
}
