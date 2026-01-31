import { performance } from "node:perf_hooks";

import { Col, Container, Row } from "react-bootstrap";

import { ColumnKey, COLUMNS_PARAM_NAME } from "@/consts";
import { resolveSelectedColumns } from "@/lib/columnSelection";
import { COLUMN_DEFINITIONS } from "@/consts.server";
import type { LedgerDateSection } from "@/types/events";

import styles from "./page.module.css";
import { LedgerEventsView } from "@/components/LedgerEventsView";
import { ColumnChooser } from "@/components/ColumnChooser";
import { UrlColumnSelectionProvider } from "@/contexts/UrlColumnSelectionContext";
import { DateChooser } from "@/components/DateChooser";

const dateKeyFor = (timestamp: string) =>
  new Date(timestamp).toISOString().slice(0, 10);

const formatDuration = (durationMs: number) => {
  if (durationMs < 1000) {
    return `${Math.round(durationMs)} ms`;
  }
  return `${(durationMs / 1000).toFixed(2)} s`;
};

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
  const selectedColumns = Array.from(
    resolveSelectedColumns(query[COLUMNS_PARAM_NAME]),
  );

  const loadStart = performance.now();

  const loadedColumns = await Promise.all(
    selectedColumns.map(async (key) => ({
      key,
      events: (await COLUMN_DEFINITIONS[key].load()).map(
        COLUMN_DEFINITIONS[key].transform,
      ),
    })),
  );

  console.log(
    `Data fetch took: ${formatDuration(performance.now() - loadStart)}`,
  );

  // Transforming loadedColumns into a structure that matches how the UI renders.
  const unorderedEventsByDate = loadedColumns.reduce(
    (acc, { key, events }) => {
      const groupedByDate = groupEventsByDate(events);
      for (const [dateKey, dateEvents] of Object.entries(groupedByDate)) {
        const bucket = acc[dateKey];
        if (bucket) {
          bucket[key] = dateEvents;
        } else {
          acc[dateKey] = { [key]: dateEvents };
        }
      }
      return acc;
    },
    {} as Record<string, Partial<Record<ColumnKey, object[]>>>,
  );

  const orderedDates = Object.keys(unorderedEventsByDate).sort((a, b) =>
    b.localeCompare(a),
  );

  const eventsByDate = orderedDates.reduce(
    (acc, dateKey) => {
      acc[dateKey] = unorderedEventsByDate[dateKey];
      return acc;
    },
    {} as Record<string, Partial<Record<ColumnKey, object[]>>>,
  );

  const eventCountsByDate = orderedDates.reduce(
    (acc, dateKey) => {
      acc[dateKey] = selectedColumns.reduce(
        (total, columnKey) =>
          total + (eventsByDate[dateKey][columnKey]?.length ?? 0),
        0,
      );
      return acc;
    },
    {} as Record<string, number>,
  );

  // const eventsByDateByColumn = new Map(
  //   loadedColumns.map(({ key, events }) => [key, groupEventsByDate(events)]),
  // );
  //
  // const orderedDates = Array.from(
  //   new Set(
  //     loadedColumns.flatMap(({ key }) =>
  //       Object.keys(eventsByDateByColumn.get(key)!),
  //     ),
  //   ),
  // ).sort((a, b) => b.localeCompare(a));

  // const sections: LedgerDateSection[] = orderedDates.map((dateKey) => {
  //   const columns = selectedColumns.map((key) => ({
  //     key,
  //     events: eventsByDateByColumn.get(key)![dateKey] ?? [],
  //   }));
  //   const count = columns.reduce(
  //     (total, column) => total + column.events.length,
  //     0,
  //   );
  //
  //   return { key: dateKey, count, columns };
  // });

  // const dateSections = sections.map(({ key, count }) => ({ key, count }));

  return (
    <div className={styles.layoutContainer}>
      <header className={styles.layoutHeader}>
        <h1>Ledger events</h1>
      </header>

      <Container fluid className={styles.layoutContent}>
        <UrlColumnSelectionProvider>
          <Row className={styles.layoutRow}>
            <Col xs={2} className={styles.layoutColumn}>
              <ColumnChooser />
              <DateChooser dates={eventCountsByDate} />
            </Col>
            <Col xs={10} className={styles.layoutColumn}>
              <p>no hejka</p>
            </Col>
          </Row>
        </UrlColumnSelectionProvider>

        {/*<LedgerEventsView*/}
        {/*  dateSections={dateSections}*/}
        {/*  sections={sections}*/}
        {/*  columnCount={selectedColumns.length}*/}
        {/*/>*/}
      </Container>
    </div>
  );
}
