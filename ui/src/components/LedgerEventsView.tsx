"use client";

import { type ReactNode } from "react";
import { Col, Row } from "react-bootstrap";

import { DateChooser } from "@/components/DateChooser";
import { EventCard } from "@/components/EventCard";
import {
  UrlColumnSelectionProvider,
  useUrlColumnSelection,
} from "@/contexts/UrlColumnSelectionContext";
import styles from "@/app/page.module.css";
import { ColumnChooser } from "@/components/ColumnChooser";
import { ColumnKey } from "@/consts";

type DateEntry = { key: string; count: number };

type EventLeg = {
  id: string;
  assetId: string;
  walletId: string;
  quantity: string;
  isFee: boolean;
};

type LedgerEvent = {
  id: string;
  timestamp: string;
  eventType: string;
  originLocation: string;
  ledgerLegs: EventLeg[];
};

type SeedEvent = {
  id: string;
  timestamp: string;
  seedEventLegs: EventLeg[];
};

type CorrectedEvent = {
  id: string;
  timestamp: string;
  eventType: string;
  originLocation: string;
  correctedLedgerLegs: EventLeg[];
};

type DateSection = {
  key: string;
  ledgerEvents: LedgerEvent[];
  seedEvents: SeedEvent[];
  correctedEvents: CorrectedEvent[];
};

type LedgerEventsViewProps = {
  dateSections: DateEntry[];
  sections: DateSection[];
};

type ColumnDefinition = {
  key: ColumnKey;
  label: string;
  render: (section: DateSection) => ReactNode;
};

const MAX_COLUMNS = 4;

const columnDefinitions: ColumnDefinition[] = [
  {
    key: "raw",
    label: "Raw events",
    render: (section) =>
      section.ledgerEvents.map((event) => (
        <EventCard
          key={event.id}
          timestamp={event.timestamp}
          eventType={event.eventType}
          place={event.originLocation}
          legs={event.ledgerLegs}
        />
      )),
  },
  {
    key: "corrections",
    label: "Corrections",
    render: (section) =>
      section.seedEvents.map((event) => (
        <EventCard
          key={event.id}
          timestamp={event.timestamp}
          eventType="seed"
          place=""
          legs={event.seedEventLegs}
        />
      )),
  },
  {
    key: "corrected",
    label: "Corrected events",
    render: (section) =>
      section.correctedEvents.map((event) => (
        <EventCard
          key={event.id}
          timestamp={event.timestamp}
          eventType={event.eventType}
          place={event.originLocation}
          legs={event.correctedLedgerLegs}
        />
      )),
  },
];

export function LedgerEventsView({
  dateSections,
  sections,
}: LedgerEventsViewProps) {
  return (
    <UrlColumnSelectionProvider>
      <LedgerEventsLayout dateSections={dateSections} sections={sections} />
    </UrlColumnSelectionProvider>
  );
}

type LedgerEventsLayoutProps = LedgerEventsViewProps;

function LedgerEventsLayout({
  dateSections,
  sections,
}: LedgerEventsLayoutProps) {
  const { selected, toggle } = useUrlColumnSelection();

  const activeColumns = columnDefinitions.filter((column) =>
    selected.has(column.key),
  );
  const columnSpan = 12 / activeColumns.length;

  return (
    <Row className={styles.layoutRow}>
      <Col xs={2} className={styles.layoutColumn}>
        <ColumnChooser
          selected={selected}
          minSelected={1}
          maxSelected={MAX_COLUMNS}
          onToggle={toggle}
        />
        <DateChooser dates={dateSections} />
      </Col>
      <Col xs={10} className={styles.layoutColumn}>
        {sections.map((section) => (
          <section
            id={`day-${section.key}`}
            key={section.key}
            className="mb-4 pb-3 border-bottom"
          >
            <h5>{section.key}</h5>
            <Row>
              {activeColumns.map((column) => (
                <Col xs={columnSpan} key={column.key}>
                  {column.render(section)}
                </Col>
              ))}
            </Row>
          </section>
        ))}
      </Col>
    </Row>
  );
}
