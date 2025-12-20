import { Col, Container, Row } from "react-bootstrap";
import { DateChooser } from "@/components/DateChooser";

import {
  getCorrectedLedgerEvents,
  getLedgerEvents,
  getSeedEvents,
} from "@/db/client";

import styles from "./page.module.css";
import { EventCard } from "@/components/EventCard";

const dateKeyFor = (timestamp: string) =>
  new Date(timestamp).toISOString().slice(0, 10);

const groupEventsByDate = <T extends { timestamp: string }>(events: T[]) => {
  const eventsByDate: Record<string, T[]> = {};

  for (const event of events) {
    const dateKey = dateKeyFor(event.timestamp);
    const bucket = eventsByDate[dateKey];
    if (bucket) {
      bucket.push(event);
    } else {
      eventsByDate[dateKey] = [event];
    }
  }

  return eventsByDate;
};

export default async function Home() {
  const [ledgerEvents, seedEvents, correctedLedgerEvents] = await Promise.all([
    getLedgerEvents(),
    getSeedEvents(),
    getCorrectedLedgerEvents(),
  ]);

  const ledgerEventsByDate = groupEventsByDate(ledgerEvents);
  const seedEventsByDate = groupEventsByDate(seedEvents);
  const correctedEventsByDate = groupEventsByDate(correctedLedgerEvents);

  const orderedDates = Array.from(
    new Set([
      ...Object.keys(ledgerEventsByDate),
      ...Object.keys(seedEventsByDate),
      ...Object.keys(correctedEventsByDate),
    ]),
  ).sort((a, b) => b.localeCompare(a));

  const dateSections = orderedDates.map((dateKey) => ({
    key: dateKey,
    count:
      (ledgerEventsByDate[dateKey]?.length ?? 0) +
      (seedEventsByDate[dateKey]?.length ?? 0) +
      (correctedEventsByDate[dateKey]?.length ?? 0),
  }));

  return (
    <div className={styles.layoutContainer}>
      <header className={styles.layoutHeader}>
        <h1>Ledger events</h1>
      </header>

      <Container fluid className={styles.layoutContent}>
        <Row className={styles.layoutRow}>
          <Col xs={2} className={styles.layoutColumn}>
            <DateChooser dates={dateSections} />
          </Col>
          <Col xs={10} className={styles.layoutColumn}>
            {orderedDates.map((dateKey) => {
              const ledgerEventsForDay = ledgerEventsByDate[dateKey] ?? [];
              const seedEventsForDay = seedEventsByDate[dateKey] ?? [];
              const correctedEventsForDay =
                correctedEventsByDate[dateKey] ?? [];

              return (
                <section
                  id={`day-${dateKey}`}
                  key={dateKey}
                  className="mb-4 pb-3 border-bottom"
                >
                  <h5>{dateKey}</h5>
                  <Row>
                    <Col xs={4}>
                      {ledgerEventsForDay.map((event) => (
                        <EventCard
                          key={event.id}
                          timestamp={event.timestamp}
                          eventType={event.eventType}
                          place={event.originLocation}
                          legs={event.ledgerLegs}
                        />
                      ))}
                    </Col>
                    <Col xs={4}>
                      {seedEventsForDay.map((event) => (
                        <EventCard
                          key={event.id}
                          timestamp={event.timestamp}
                          eventType="seed"
                          place=""
                          legs={event.seedEventLegs}
                        />
                      ))}
                    </Col>
                    <Col xs={4}>
                      {correctedEventsForDay.map((event) => (
                        <EventCard
                          key={event.id}
                          timestamp={event.timestamp}
                          eventType={event.eventType}
                          place={event.originLocation}
                          legs={event.correctedLedgerLegs}
                        />
                      ))}
                    </Col>
                  </Row>
                </section>
              );
            })}
          </Col>
        </Row>
      </Container>
    </div>
  );
}
