"use client";

import { type ReactNode } from "react";
import { Col, Row } from "react-bootstrap";

import { DateChooser } from "@/components/DateChooser";
import { UrlColumnSelectionProvider } from "@/contexts/UrlColumnSelectionContext";
import styles from "@/app/page.module.css";
import { ColumnChooser } from "@/components/ColumnChooser";

type DateEntry = { key: string; count: number };

type LedgerEventsViewProps = {
  dateSections: DateEntry[];
  children: ReactNode;
};

export function LedgerEventsView({
  dateSections,
  children,
}: LedgerEventsViewProps) {
  return (
    <UrlColumnSelectionProvider>
      <Row className={styles.layoutRow}>
        <Col xs={2} className={styles.layoutColumn}>
          <ColumnChooser />
          <DateChooser dates={dateSections} />
        </Col>
        <Col xs={10} className={styles.layoutColumn}>
          {children}
        </Col>
      </Row>
    </UrlColumnSelectionProvider>
  );
}
