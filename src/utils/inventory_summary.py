from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable

from domain.inventory import InventoryEngine, OpenLotSnapshot
from domain.pricing import PriceProvider

from .formatting import format_currency, format_decimal


@dataclass
class AssetInventorySummary:
    asset_id: str
    total_quantity: Decimal
    tax_free_quantity: Decimal
    taxable_quantity: Decimal
    total_value_eur: Decimal
    tax_free_value_eur: Decimal
    taxable_value_eur: Decimal
    lots: int


@dataclass
class InventorySummary:
    as_of: datetime
    assets: list[AssetInventorySummary] = field(default_factory=list)
    total_value_eur: Decimal = Decimal("0")
    total_tax_free_value_eur: Decimal = Decimal("0")

    @property
    def total_taxable_value_eur(self) -> Decimal:
        return self.total_value_eur - self.total_tax_free_value_eur


def compute_inventory_summary(
    open_inventory: Iterable[OpenLotSnapshot],
    *,
    price_provider: PriceProvider,
    as_of: datetime | None = None,
    tax_free_days: int = 365,
) -> InventorySummary:
    now = as_of or datetime.now(timezone.utc)
    tax_free_cutoff = now - timedelta(days=tax_free_days)

    accumulators: dict[str, tuple[Decimal, Decimal, int]] = {}

    for lot in open_inventory:
        if lot.quantity_remaining <= 0:
            continue
        totals, tax_free_totals, lots = accumulators.get(lot.asset_id, (Decimal("0"), Decimal("0"), 0))
        totals += lot.quantity_remaining
        if lot.acquired_timestamp <= tax_free_cutoff:
            tax_free_totals += lot.quantity_remaining
        accumulators[lot.asset_id] = totals, tax_free_totals, lots + 1

    summaries: list[AssetInventorySummary] = []
    total_value = Decimal("0")
    total_tax_free_value = Decimal("0")

    for asset_id in sorted(accumulators):
        total_qty, tax_free_qty, lots = accumulators[asset_id]
        taxable_qty = total_qty - tax_free_qty
        rate = price_provider.rate(asset_id, InventoryEngine.EUR_ASSET_ID, now)
        value_total = total_qty * rate
        value_tax_free = tax_free_qty * rate
        value_taxable = value_total - value_tax_free

        total_value += value_total
        total_tax_free_value += value_tax_free

        summaries.append(
            AssetInventorySummary(
                asset_id=asset_id,
                total_quantity=total_qty,
                tax_free_quantity=tax_free_qty,
                taxable_quantity=taxable_qty,
                total_value_eur=value_total,
                tax_free_value_eur=value_tax_free,
                taxable_value_eur=value_taxable,
                lots=lots,
            )
        )

    return InventorySummary(
        as_of=now,
        assets=summaries,
        total_value_eur=total_value,
        total_tax_free_value_eur=total_tax_free_value,
    )


def render_inventory_summary(summary: InventorySummary) -> None:
    print("Open inventory by asset:")
    if not summary.assets:
        print("  (empty)")
        return

    quantity_label = "Quantity (total/free/taxable)"
    value_label = "Value EUR (total/free/taxable)"

    rows: list[tuple[str, str, str, int]] = []
    for asset in summary.assets:
        quantities_text = (
            f"{format_decimal(asset.total_quantity)} / "
            f"{format_decimal(asset.tax_free_quantity)} / "
            f"{format_decimal(asset.taxable_quantity)}"
        )
        values_text = (
            f"{format_currency(asset.total_value_eur)} / "
            f"{format_currency(asset.tax_free_value_eur)} / "
            f"{format_currency(asset.taxable_value_eur)}"
        )
        rows.append((asset.asset_id, quantities_text, values_text, asset.lots))

    asset_width = max(len("Asset"), max((len(asset) for asset, _, _, _ in rows), default=0))
    quantity_width = max(len(quantity_label), max((len(qty) for _, qty, _, _ in rows), default=0))
    value_width = max(len(value_label), max((len(val) for _, _, val, _ in rows), default=0))
    lots_width = max(len("Lots"), max((len(str(lots)) for _, _, _, lots in rows), default=0))

    header = (
        f"{'Asset':<{asset_width}} "
        f"{quantity_label:>{quantity_width}} "
        f"{value_label:>{value_width}} "
        f"{'Lots':>{lots_width}}"
    )

    lines = [header, "-" * len(header)]

    for asset_id, quantities_text, values_text, lots in rows:
        lines.append(
            f"{asset_id:<{asset_width}} "
            f"{quantities_text:>{quantity_width}} "
            f"{values_text:>{value_width}} "
            f"{lots:>{lots_width}}"
        )

    lines.append("-" * len(header))
    total_value_text = (
        f"{format_currency(summary.total_value_eur)} / "
        f"{format_currency(summary.total_tax_free_value_eur)} / "
        f"{format_currency(summary.total_taxable_value_eur)}"
    )
    lines.append(
        f"{'TOTAL':<{asset_width}} {'':>{quantity_width}} {total_value_text:>{value_width}} {'':>{lots_width}}"
    )

    print("\n".join(lines))
