// This file is completely vibed and I didn't read it.
"use client";

import { useState } from "react";

import { Badge, Button, Card, Collapse, Table } from "react-bootstrap";

import type {
  SystemState,
  SystemStateStage,
  SystemStateStatus,
} from "@/types/systemState";

import styles from "./SystemStateSection.module.css";

type SystemStateSectionProps = {
  state: SystemState;
};

const STATUS_META: Record<
  SystemStateStatus,
  {
    label: string;
    badge: "secondary" | "primary" | "success" | "danger";
    toneClassName: string;
    description: string;
  }
> = {
  NOT_RUN: {
    label: "Not run",
    badge: "secondary",
    toneClassName: "text-muted",
    description: "No main pipeline run has been persisted yet.",
  },
  RUNNING: {
    label: "Running",
    badge: "primary",
    toneClassName: "text-primary",
    description: "The latest main pipeline run is in progress.",
  },
  COMPLETED: {
    label: "Completed",
    badge: "success",
    toneClassName: "text-success",
    description: "The latest main pipeline run completed successfully.",
  },
  FAILED: {
    label: "Failed",
    badge: "danger",
    toneClassName: "text-danger",
    description: "The latest main pipeline run failed.",
  },
};

const STAGE_LABELS: Record<SystemStateStage, string> = {
  RAW_IMPORT: "Raw import",
  CORRECTIONS: "Corrections",
  WALLET_PROJECTION: "Wallet projection",
  ACQUISITION_DISPOSAL: "Acquisition/disposal",
  TAX_COMPUTATION: "Tax computation",
};

const formatDateTime = (value: string | null) => {
  if (!value) {
    return "None";
  }

  const date = new Date(value);
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  const hours = String(date.getUTCHours()).padStart(2, "0");
  const minutes = String(date.getUTCMinutes()).padStart(2, "0");
  const seconds = String(date.getUTCSeconds()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds} UTC`;
};

const formatStage = (stage: SystemStateStage | null) =>
  stage ? STAGE_LABELS[stage] : "None";

export function SystemStateSection({ state }: SystemStateSectionProps) {
  const [open, setOpen] = useState(state.status === "FAILED");
  const statusMeta = STATUS_META[state.status];

  return (
    <Card className="border-0 shadow-sm">
      <Card.Header className="bg-white border-0 p-0">
        <Button
          type="button"
          variant="link"
          onClick={() => setOpen((current) => !current)}
          aria-expanded={open}
          className="w-100 d-flex align-items-center gap-2 px-3 px-lg-4 py-2 text-decoration-none text-start text-body"
        >
          <span className="fw-semibold">System state</span>
          <Badge bg={statusMeta.badge} className="ms-auto">
            {statusMeta.label}
          </Badge>
          <span className="small text-muted">
            {open ? "Collapse" : "Expand"}
          </span>
        </Button>
      </Card.Header>
      <Collapse in={open}>
        <div>
          <Card.Body className="px-3 pb-3 pt-0 px-lg-4 pb-lg-4">
            <p className={`small mb-3 mt-3 ${statusMeta.toneClassName}`}>
              {statusMeta.description}
            </p>
            <Table responsive size="sm" className="mb-4 align-middle">
              <tbody>
                <tr>
                  <th scope="row">Stage</th>
                  <td>{formatStage(state.stage)}</td>
                </tr>
                <tr>
                  <th scope="row">Started</th>
                  <td>{formatDateTime(state.startedAt)}</td>
                </tr>
                <tr>
                  <th scope="row">Finished</th>
                  <td>{formatDateTime(state.finishedAt)}</td>
                </tr>
              </tbody>
            </Table>

            {state.error && (
              <section className="mb-4">
                <div className="small text-uppercase text-muted mb-2">
                  Error
                </div>
                <div className="mb-2">
                  <Badge bg="danger">{state.error.exceptionType}</Badge>
                </div>
                <p className="mb-0">{state.error.message}</p>
              </section>
            )}

            {state.error?.traceback && (
              <section>
                <div className="small text-uppercase text-muted mb-2">
                  Traceback
                </div>
                <pre
                  className={`${styles.traceback} small bg-light border rounded p-3 mb-0`}
                >
                  {state.error.traceback}
                </pre>
              </section>
            )}
          </Card.Body>
        </div>
      </Collapse>
    </Card>
  );
}
