from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from domain.inventory import InventoryEngine
from domain.ledger import LedgerEvent
from domain.pricing import PriceProvider

from .formatting import format_currency, format_decimal


@dataclass
class AssetInventorySummary:
    asset_id: str
    total_quantity: Decimal
    total_value_eur: Decimal


@dataclass
class InventorySummary:
    as_of: datetime
    assets: list[AssetInventorySummary] = field(default_factory=list)


def compute_inventory_summary(
    events: Iterable[LedgerEvent],
    owned_wallet_ids: set[str],
    *,
    price_provider: PriceProvider,
    as_of: datetime | None = None,
) -> InventorySummary:
    now = as_of or datetime.now(timezone.utc)

    balances: dict[str, Decimal] = {}
    for event in events:
        for leg in event.legs:
            if leg.wallet_id not in owned_wallet_ids:
                continue
            balances[leg.asset_id] = balances.get(leg.asset_id, Decimal("0")) + leg.quantity

    asset_rates: dict[str, Decimal] = {}
    for asset_id, quantity in balances.items():
        if quantity > 0:
            asset_rates[asset_id] = price_provider.rate(asset_id, InventoryEngine.EUR_ASSET_ID, now)

    summaries: list[AssetInventorySummary] = []

    for asset_id in sorted(asset_rates):
        total_qty = balances[asset_id]
        rate = asset_rates[asset_id]
        value_total = total_qty * rate

        summaries.append(
            AssetInventorySummary(
                asset_id=asset_id,
                total_quantity=total_qty,
                total_value_eur=value_total,
            )
        )

    return InventorySummary(
        as_of=now,
        assets=summaries,
    )


def render_inventory_summary(summary: InventorySummary) -> None:
    print("Open inventory:")
    if not summary.assets:
        print("  (empty)")
        return

    quantity_label = "Quantity"
    value_label = "Value EUR"

    rows: list[tuple[str, str, str]] = []
    for asset in summary.assets:
        quantities_text = f"{format_decimal(asset.total_quantity)}"
        values_text = f"{format_currency(asset.total_value_eur)}"
        rows.append((asset.asset_id, quantities_text, values_text))

    asset_width = max(len("Asset"), max((len(asset) for asset, _, _ in rows), default=0))
    quantity_width = max(len(quantity_label), max((len(qty) for _, qty, _ in rows), default=0))
    value_width = max(len(value_label), max((len(val) for _, _, val in rows), default=0))

    header = f"{'Asset':<{asset_width}} {quantity_label:>{quantity_width}} {value_label:>{value_width}}"

    lines = [header, "-" * len(header)]

    for asset_id, quantities_text, values_text in rows:
        lines.append(f"{asset_id:<{asset_width}} {quantities_text:>{quantity_width}} {values_text:>{value_width}}")

    lines.append("-" * len(header))
    print("\n".join(lines))
