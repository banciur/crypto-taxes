// This file is completely vibed and I didn't read it.
"use client";

import { Table } from "react-bootstrap";

import { useAccountNames } from "@/contexts/AccountNamesContext";
import { formatDecimalString } from "@/lib/decimalStrings";
import type { WalletTrackingBalance } from "@/types/walletTracking";

type WalletTrackingBalancesTableProps = {
  balances: WalletTrackingBalance[];
};

export function WalletTrackingBalancesTable({
  balances,
}: WalletTrackingBalancesTableProps) {
  const { resolveAccountName } = useAccountNames();

  if (balances.length === 0) {
    return <div className="small text-muted">No non-zero balances.</div>;
  }

  return (
    <Table responsive hover size="sm" className="mb-0 align-middle">
      <thead>
        <tr>
          <th>Account</th>
          <th>Asset</th>
          <th className="text-end">Balance</th>
        </tr>
      </thead>
      <tbody>
        {balances.map((balance) => (
          <tr key={`${balance.accountChainId}:${balance.assetId}`}>
            <td>
              <div className="fw-semibold">
                {resolveAccountName(balance.accountChainId)}
              </div>
              <div className="small text-muted">{balance.accountChainId}</div>
            </td>
            <td className="fw-semibold">{balance.assetId}</td>
            <td className="text-end">{formatDecimalString(balance.balance)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
