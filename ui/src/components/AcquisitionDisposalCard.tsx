// This file is completely vibed and I didn't read it.
"use client";

import { Badge, Card, CardBody, CardHeader } from "react-bootstrap";
import { clsx } from "clsx";

import { OriginIcon } from "@/components/OriginIcon";
import { OriginId } from "@/components/OriginId";
import { useAccountNames } from "@/contexts/AccountNamesContext";
import {
  divideDecimalStrings,
  formatDecimalString,
  getDecimalStringSign,
  subtractDecimalStrings,
} from "@/lib/decimalStrings";
import type {
  AcquisitionDisposalItemData,
  DisposalItemData,
} from "@/types/events";

type AcquisitionDisposalCardProps = {
  item: AcquisitionDisposalItemData;
};

const timeLabel = (timestamp: string) =>
  new Date(timestamp).toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

function DetailRow({
  label,
  value,
  valueClassName,
}: {
  label: string;
  value: string;
  valueClassName?: string;
}) {
  return (
    <div className="d-flex justify-content-between gap-3">
      <span className="text-muted small">{label}</span>
      <span className={clsx("small font-monospace text-end", valueClassName)}>
        {value}
      </span>
    </div>
  );
}

function DisposalDetails({ item }: { item: DisposalItemData }) {
  // Cost basis per unit recovers the consumed lot's acquisition cost per unit
  // (cost_basis_total = quantity_used * lot.cost_per_unit on the backend).
  const costPerUnit = divideDecimalStrings(
    item.costBasisTotal,
    item.quantityUsed,
  );
  const gain = subtractDecimalStrings(item.proceedsTotal, item.costBasisTotal);
  const gainSign = getDecimalStringSign(gain);
  const gainClassName =
    gainSign > 0 ? "text-success" : gainSign < 0 ? "text-danger" : undefined;

  return (
    <>
      <DetailRow
        label="Quantity used"
        value={formatDecimalString(item.quantityUsed)}
      />
      <DetailRow label="Cost / unit" value={formatDecimalString(costPerUnit)} />
      <DetailRow
        label="Proceeds"
        value={formatDecimalString(item.proceedsTotal)}
      />
      <DetailRow
        label="Cost basis"
        value={formatDecimalString(item.costBasisTotal)}
      />
      <DetailRow
        label="Gain / loss"
        value={formatDecimalString(gain)}
        valueClassName={gainClassName}
      />
    </>
  );
}

export function AcquisitionDisposalCard({
  item,
}: AcquisitionDisposalCardProps) {
  const { resolveAccountName } = useAccountNames();
  const place = item.eventOrigin.location.toLowerCase();
  const originId = item.eventOrigin.externalId;

  return (
    <Card className="shadow-sm">
      <CardHeader className="d-flex flex-wrap align-items-center gap-2">
        {item.kind === "ACQUISITION" ? (
          <Badge bg="success">Acquisition</Badge>
        ) : (
          <Badge bg="warning" text="dark">
            Disposal
          </Badge>
        )}
        {originId && (
          <OriginId
            originId={originId}
            place={place}
            className="text-muted small"
          />
        )}
        <span className="text-muted small">{timeLabel(item.timestamp)}</span>
        <OriginIcon place={place} className="ms-auto flex-shrink-0" />
      </CardHeader>
      <CardBody className="d-flex flex-column gap-1">
        <div className="d-flex justify-content-between align-items-center">
          <span className="fw-semibold">{item.assetId}</span>
          {item.isFee && <Badge bg="secondary">Fee</Badge>}
        </div>
        <div className="small text-muted">
          {resolveAccountName(item.accountChainId)}
        </div>
        {item.kind === "ACQUISITION" ? (
          <>
            <DetailRow
              label="Quantity acquired"
              value={formatDecimalString(item.quantityAcquired)}
            />
            <DetailRow
              label="Cost / unit"
              value={formatDecimalString(item.costPerUnit)}
            />
          </>
        ) : (
          <DisposalDetails item={item} />
        )}
      </CardBody>
    </Card>
  );
}
