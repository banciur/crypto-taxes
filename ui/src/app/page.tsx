import { Container } from "react-bootstrap";

import { COLUMNS_PARAM_NAME } from "@/consts";
import { EventCard } from "@/components/EventCard";
import { resolveSelectedColumns } from "@/lib/columnSelection";
import { COLUMN_DEFINITIONS } from "@/consts.server";

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

export default async function Home({ searchParams }: PageProps<"/">) {
  const query = await searchParams;
  const selectedColumns = resolveSelectedColumns(query[COLUMNS_PARAM_NAME]);

  const loadedColumns = await Promise.all(
    selectedColumns.values().map(async (key) => ({
      key,
      events: await COLUMN_DEFINITIONS[key].load(),
    })),
  );

  const eventsByDateByColumn = new Map(
    loadedColumns.map(({ key, events }) => [key, groupEventsByDate(events)]),
  );

  const orderedDates = Array.from(
    new Set(
      loadedColumns.flatMap(({ key }) =>
        Object.keys(eventsByDateByColumn.get(key)!),
      ),
    ),
  ).sort((a, b) => b.localeCompare(a));

  const dateSections = orderedDates.map((dateKey) => ({
    key: dateKey,
    count: loadedColumns.reduce((total, { key }) => {
      const eventsByDate = eventsByDateByColumn.get(key)!;
      return total + (eventsByDate[dateKey]?.length ?? 0);
    }, 0),
  }));

  return (
    <div className={styles.layoutContainer}>
      <header className={styles.layoutHeader}>
        <h1>Ledger events</h1>
      </header>

      <Container fluid className={styles.layoutContent}>
        <LedgerEventsView dateSections={dateSections}>
          {orderedDates.map((dateKey) => (
            <section
              id={`day-${dateKey}`}
              key={dateKey}
              className="mb-4 pb-3 border-bottom"
            >
              <h5>{dateKey}</h5>
              <div className="row">
                {Array.from(selectedColumns).map((key) => (
                  <div className={`col-${12 / selectedColumns.size}`} key={key}>
                    {(eventsByDateByColumn.get(key)![dateKey] ?? []).map(
                      (event) => (
                        <EventCard
                          key={(event as { id: string }).id}
                          {...COLUMN_DEFINITIONS[key].transform(event)}
                        />
                      ),
                    )}
                  </div>
                ))}
              </div>
            </section>
          ))}
        </LedgerEventsView>
      </Container>
    </div>
  );
}
