// This file is completely vibed and I didn't read it.
"use client";

import { Table } from "react-bootstrap";

import { OriginId } from "@/components/OriginId";
import { useAccountNames } from "@/contexts/AccountNamesContext";
import { formatDecimalString } from "@/lib/decimalStrings";
import type { WalletTrackingIssue } from "@/types/walletTracking";

type WalletTrackingIssueListProps = {
  issues: WalletTrackingIssue[];
};

export function WalletTrackingIssueList({
  issues,
}: WalletTrackingIssueListProps) {
  const { resolveAccountName } = useAccountNames();

  return (
    <Table responsive bordered size="sm" className="mb-0 align-middle">
      <thead>
        <tr>
          <th>Event</th>
          <th>Account</th>
          <th>Asset</th>
          <th className="text-end">Attempted delta</th>
          <th className="text-end">Available</th>
          <th className="text-end">Missing</th>
        </tr>
      </thead>
      <tbody>
        {issues.map((issue, index) => (
          <tr
            key={`${issue.event.location}:${issue.event.externalId}:${issue.accountChainId}:${issue.assetId}:${index}`}
          >
            <td>
              <div className="small text-uppercase text-muted">
                {issue.event.location}
              </div>
              <OriginId
                originId={issue.event.externalId}
                place={issue.event.location.toLowerCase()}
                className="small"
              />
            </td>
            <td>
              <div className="fw-semibold">
                {resolveAccountName(issue.accountChainId)}
              </div>
              <div className="small text-muted">{issue.accountChainId}</div>
            </td>
            <td className="fw-semibold">{issue.assetId}</td>
            <td className="text-end">
              {formatDecimalString(issue.attemptedDelta)}
            </td>
            <td className="text-end">
              {formatDecimalString(issue.availableBalance)}
            </td>
            <td className="text-end text-danger fw-semibold">
              {formatDecimalString(issue.missingBalance)}
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
