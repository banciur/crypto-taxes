import { performance } from "node:perf_hooks";

import { Col, Container, Row } from "react-bootstrap";

import { getAccounts } from "@/api/accounts";
import { COLUMNS_PARAM_NAME } from "@/consts";
import { resolveSelectedColumns } from "@/lib/columnSelection";
import {
  dayKeyForTimestampBucket,
  timestampBucketKeyFor,
} from "@/lib/timestampBuckets";
import { COLUMN_DEFINITIONS } from "@/consts.server";
import type { EventsByTimestamp } from "@/types/events";

import styles from "./page.module.css";
import { AccountNamesProvider } from "@/contexts/AccountNamesContext";
import { ColumnChooser } from "@/components/ColumnChooser";
import { UrlColumnSelectionProvider } from "@/contexts/UrlColumnSelectionContext";
import { DateChooser } from "@/components/DateChooser";
import { Events } from "@/components/Events";
import { VisibleDayProvider } from "@/contexts/VisibleDayContext";

const formatDuration = (durationMs: number) => {
  if (durationMs < 1000) {
    return `${Math.round(durationMs)} ms`;
  }
  return `${(durationMs / 1000).toFixed(2)} s`;
};

const groupEventsByTimestamp = <T extends { timestamp: string }>(
  events: T[],
) => {
  const eventsByTimestamp: Record<string, T[]> = {};

  for (const event of events) {
    const timestampBucket = timestampBucketKeyFor(event.timestamp);
    const bucket = eventsByTimestamp[timestampBucket];
    if (bucket) {
      bucket.push(event);
    } else {
      eventsByTimestamp[timestampBucket] = [event];
    }
  }

  return eventsByTimestamp;
};

export default async function Home({ searchParams }: PageProps<"/">) {
  const query = await searchParams;
  const selectedColumns = Array.from(
    resolveSelectedColumns(query[COLUMNS_PARAM_NAME]),
  );

  const accountsLoadStart = performance.now();
  const accounts = await getAccounts();

  const columnsLoadStart = performance.now();
  console.log(
    `Accounts fetch took: ${formatDuration(
      columnsLoadStart - accountsLoadStart,
    )}`,
  );

  const loadedColumns = await Promise.all(
    selectedColumns.map(async (key) => ({
      key,
      events: await COLUMN_DEFINITIONS[key].load(),
    })),
  );

  console.log(
    `Column fetch took: ${formatDuration(
      performance.now() - columnsLoadStart,
    )}`,
  );

  // Transforming loadedColumns into a structure that matches how the UI renders.
  const unorderedEventsByTimestamp = loadedColumns.reduce(
    (acc, { key, events }) => {
      const groupedByTimestamp = groupEventsByTimestamp(events);
      for (const [timestampBucket, bucketEvents] of Object.entries(
        groupedByTimestamp,
      )) {
        const bucket = acc[timestampBucket];
        if (bucket) {
          bucket[key] = bucketEvents;
        } else {
          acc[timestampBucket] = { [key]: bucketEvents };
        }
      }
      return acc;
    },
    {} as EventsByTimestamp,
  );

  const orderedTimestampBuckets = Object.keys(unorderedEventsByTimestamp).sort(
    (a, b) => Number(b) - Number(a),
  );

  const eventsByTimestamp: EventsByTimestamp = {};
  const eventCountsByDate: Record<string, number> = {};

  for (const timestampBucket of orderedTimestampBuckets) {
    const bucketEvents = unorderedEventsByTimestamp[timestampBucket];
    const dayKey = dayKeyForTimestampBucket(timestampBucket);
    const eventCount = selectedColumns.reduce(
      (total, columnKey) => total + (bucketEvents[columnKey]?.length ?? 0),
      0,
    );

    eventsByTimestamp[timestampBucket] = bucketEvents;
    eventCountsByDate[dayKey] = (eventCountsByDate[dayKey] ?? 0) + eventCount;
  }

  return (
    <div className={styles.layoutContainer}>
      <header className={styles.layoutHeader}>
        <h1>Ledger events</h1>
      </header>
      <Container fluid className={styles.layoutContent}>
        <AccountNamesProvider accounts={accounts}>
          <UrlColumnSelectionProvider>
            <VisibleDayProvider>
              <Row className={styles.layoutRow}>
                <Col xs={2} className={styles.layoutColumn}>
                  <ColumnChooser />
                  <DateChooser dates={eventCountsByDate} />
                </Col>
                <Col xs={10} className={styles.layoutColumn}>
                  <Events eventsByTimestamp={eventsByTimestamp} />
                </Col>
              </Row>
            </VisibleDayProvider>
          </UrlColumnSelectionProvider>
        </AccountNamesProvider>
      </Container>
    </div>
  );
}
