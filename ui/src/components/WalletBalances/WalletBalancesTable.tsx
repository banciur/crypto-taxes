"use client";

import Link from "next/link";
import { Table } from "react-bootstrap";

import { useAccountNames } from "@/contexts/AccountNamesContext";
import { useAssetFilter } from "@/hooks/useAssetFilter";
import { formatDecimalString } from "@/lib/decimalStrings";
import type { WalletBalance } from "@/types/walletBalances";

type WalletBalancesTableProps = {
  balances: WalletBalance[];
};

export function WalletBalancesTable({ balances }: WalletBalancesTableProps) {
  const { resolveAccountName } = useAccountNames();
  const { assetFilter, hrefForAssetFilter } = useAssetFilter();

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
        {balances.map((balance) => {
          const isFiltered = assetFilter === balance.assetId;

          return (
            <tr key={`${balance.accountChainId}:${balance.assetId}`}>
              <td>
                <div className="fw-semibold">
                  {resolveAccountName(balance.accountChainId)}
                </div>
                <div className="small text-muted">{balance.accountChainId}</div>
              </td>
              <td className="fw-semibold">
                <Link
                  href={hrefForAssetFilter(isFiltered ? null : balance.assetId)}
                  scroll={false}
                  aria-current={isFiltered ? "true" : undefined}
                  title={
                    isFiltered
                      ? "Clear the asset filter"
                      : `Filter events by ${balance.assetId}`
                  }
                >
                  {balance.assetId}
                </Link>
              </td>
              <td className="text-end">
                {formatDecimalString(balance.balance)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}
