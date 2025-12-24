import { Container } from "react-bootstrap";

import {
  getCorrectedLedgerEvents,
  getLedgerEvents,
  getSeedEvents,
} from "@/db/client";

import styles from "./page.module.css";
import { LedgerEventsView } from "@/components/LedgerEventsView";

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

  const eventSections = orderedDates.map((dateKey) => ({
    key: dateKey,
    ledgerEvents: ledgerEventsByDate[dateKey] ?? [],
    seedEvents: seedEventsByDate[dateKey] ?? [],
    correctedEvents: correctedEventsByDate[dateKey] ?? [],
  }));

  return (
    <div className={styles.layoutContainer}>
      <header className={styles.layoutHeader}>
        <h1>Ledger events</h1>
      </header>

      <Container fluid className={styles.layoutContent}>
        <LedgerEventsView
          dateSections={dateSections}
          sections={eventSections}
        />
      </Container>
    </div>
  );
}
