"use client";

import { useState } from "react";

import { Button, Card, Collapse } from "react-bootstrap";

import type { WalletBalance } from "@/types/walletBalances";
import { WalletBalancesTable } from "./WalletBalancesTable";

type WalletBalancesSectionProps = {
  balances: WalletBalance[];
};

export function WalletBalancesSection({
  balances,
}: WalletBalancesSectionProps) {
  const [open, setOpen] = useState(false);

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
          <span className="fw-semibold">Wallet balances</span>
          <span className="small text-muted ms-auto">
            {open ? "Collapse" : "Expand"}
          </span>
        </Button>
      </Card.Header>
      <Collapse in={open}>
        <div>
          <Card.Body className="px-3 pb-3 pt-0 px-lg-4 pb-lg-4">
            <WalletBalancesTable balances={balances} />
          </Card.Body>
        </div>
      </Collapse>
    </Card>
  );
}
