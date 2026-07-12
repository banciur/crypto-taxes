// This file is completely vibed and I didn't read it.
"use client";

import Link from "next/link";
import { Alert } from "react-bootstrap";

import {
  ASSET_FILTERED_COLUMNS,
  AVAILABLE_COLUMNS,
  COLUMN_METADATA,
  orderColumnKeys,
  type ColumnKey,
} from "@/consts";
import { useAssetFilter } from "@/hooks/useAssetFilter";

const labelList = (columnKeys: Iterable<ColumnKey>) =>
  orderColumnKeys(columnKeys)
    .map((columnKey) => COLUMN_METADATA[columnKey].label)
    .join(", ");

export function AssetFilterNotice() {
  const { assetFilter, hrefForAssetFilter } = useAssetFilter();

  if (assetFilter === null) {
    return null;
  }

  const filteredLanes = labelList(ASSET_FILTERED_COLUMNS);
  const unfilteredLanes = labelList(
    AVAILABLE_COLUMNS.difference(ASSET_FILTERED_COLUMNS),
  );

  return (
    <Alert variant="warning" className="mb-0">
      <div className="d-flex align-items-baseline gap-3">
        <div>
          <span className="fw-semibold">Filtering by {assetFilter}.</span> Only{" "}
          {filteredLanes} are limited to items holding {assetFilter};{" "}
          {unfilteredLanes} and wallet balances still show every asset. Events
          are matched whole, so a shown card still lists its legs in other
          assets. A correction matches on its own legs or on the raw events it
          claims, so a discard of a matching event stays visible.
        </div>
        <Link
          href={hrefForAssetFilter(null)}
          scroll={false}
          className="alert-link ms-auto text-nowrap"
        >
          Clear filter
        </Link>
      </div>
    </Alert>
  );
}
