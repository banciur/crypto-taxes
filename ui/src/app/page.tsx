import { Container } from "react-bootstrap";

import { COLUMNS_PARAM_NAME } from "@/consts";
import { resolveSelectedColumns } from "@/lib/columnSelection";
import { COLUMN_DEFINITIONS } from "@/lib/ledgerColumns.server";

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

  const selectedDefinitions = COLUMN_DEFINITIONS.filter((definition) =>
    selectedColumns.has(definition.key),
  );

  const loadedColumns = await Promise.all(
    selectedDefinitions.map(async (definition) => ({
      definition,
      events: await definition.load(),
    })),
  );

  const eventsByDateByColumn = new Map(
    loadedColumns.map(
      ({ definition, events }) =>
        [definition.key, groupEventsByDate(events)] as const,
    ),
  );

  const orderedDates = Array.from(
    new Set(
      loadedColumns.flatMap(({ definition }) =>
        Object.keys(eventsByDateByColumn.get(definition.key)!),
      ),
    ),
  ).sort((a, b) => b.localeCompare(a));

  const dateSections = orderedDates.map((dateKey) => ({
    key: dateKey,
    count: loadedColumns.reduce((total, { definition }) => {
      const eventsByDate = eventsByDateByColumn.get(definition.key)!;
      return total + (eventsByDate[dateKey]?.length ?? 0);
    }, 0),
  }));

  const columnSpan = 12 / selectedDefinitions.length;
  const columnClassName = `col-${columnSpan}`;

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
                {selectedDefinitions.map((definition) => {
                  const eventsByDate = eventsByDateByColumn.get(
                    definition.key,
                  )!;
                  const events = eventsByDate[dateKey] ?? [];

                  return (
                    <div className={columnClassName} key={definition.key}>
                      {definition.render(events)}
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </LedgerEventsView>
      </Container>
    </div>
  );
}
