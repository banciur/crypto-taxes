"use client";

import { ListGroup, ListGroupItem } from "react-bootstrap";

import { clsx } from "clsx";
import { useAccountNames } from "@/contexts/AccountNamesContext";
import { getLedgerLegQuantityPresentation } from "@/lib/ledgerLegQuantity";
import type { LedgerLeg } from "@/types/events";
import styles from "./LedgerLegList.module.css";

type LedgerLegListProps = {
  legs: readonly LedgerLeg[];
  className?: string;
  itemClassName?: string;
};

export function LedgerLegList({
  legs,
  className,
  itemClassName,
}: LedgerLegListProps) {
  const { resolveAccountName } = useAccountNames();

  return (
    <ListGroup variant="flush" className={clsx("border rounded", className)}>
      {legs.map((leg) => {
        const quantityPresentation = getLedgerLegQuantityPresentation(leg);

        return (
          <ListGroupItem
            key={leg.id}
            className={clsx(
              "d-flex align-items-center gap-1",
              styles.item,
              itemClassName,
            )}
          >
            <span title={leg.accountChainId}>
              {resolveAccountName(leg.accountChainId)}
            </span>
            <span>{leg.assetId}</span>
            <span
              className={clsx("flex-shrink-0", quantityPresentation.className)}
            >
              {quantityPresentation.text}
            </span>
          </ListGroupItem>
        );
      })}
    </ListGroup>
  );
}
