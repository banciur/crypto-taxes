// This file is completely vibed and I didn't read it.
"use client";

import { useState } from "react";

import { Badge, Button, Card, Collapse } from "react-bootstrap";

import type {
  WalletProjectionState,
  WalletProjectionStatus,
} from "@/types/walletProjection";
import { WalletProjectionPanel } from "./WalletProjectionPanel";

type WalletProjectionSectionProps = {
  state: WalletProjectionState;
};

const STATUS_META: Record<
  WalletProjectionStatus,
  {
    label: string;
    badge: "secondary" | "success" | "danger";
  }
> = {
  NOT_RUN: {
    label: "Not run",
    badge: "secondary",
  },
  COMPLETED: {
    label: "Completed",
    badge: "success",
  },
  FAILED: {
    label: "Failed",
    badge: "danger",
  },
};

export function WalletProjectionSection({
  state,
}: WalletProjectionSectionProps) {
  const [open, setOpen] = useState(false);
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
          <span className="fw-semibold">Wallet projection</span>
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
            <WalletProjectionPanel state={state} />
          </Card.Body>
        </div>
      </Collapse>
    </Card>
  );
}
