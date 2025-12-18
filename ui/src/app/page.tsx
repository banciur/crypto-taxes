import { Col, Container, Row } from "react-bootstrap";

import { DateChooser } from "@/components/DateChooser";
import { LedgerEvent } from "@/components/LedgerEvent";
import type { LedgerEventWithLegs } from "@/db/client";
import { getLedgerEvents } from "@/db/client";

import styles from "./page.module.css";

export default async function Home() {
  console.time("get raw events");
  const rawEvents = await getLedgerEvents();
  console.timeEnd("get raw events");

  const grouped = rawEvents.reduce<{
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
    <div className={styles.layoutContainer}>
      <header className={styles.layoutHeader}>
        <h1>Ledger events</h1>
      </header>

      <Container fluid className={styles.layoutContent}>
        <Row className={styles.layoutRow}>
          <Col md={3} lg={2} className={styles.layoutColumn}>
            <DateChooser dates={dateSections} />
          </Col>
          <Col md={9} lg={10} className={styles.layoutColumn}>
            {grouped.order.map((dateKey) => (
              <Row id={`day-${dateKey}`} key={dateKey}>
                <Col className="d-flex flex-column gap-3 mb-3">
                  {grouped.eventsByDate[dateKey].map((event) => (
                    <LedgerEvent event={event} key={event.id} />
                  ))}
                </Col>
                <Col></Col>
              </Row>
            ))}
          </Col>
        </Row>
      </Container>
    </div>
  );
}
