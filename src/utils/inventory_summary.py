from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from domain.inventory import InventoryEngine
from domain.pricing import PriceProvider
from domain.wallet_balance_tracker import WalletBalanceTracker

from .formatting import format_currency, format_decimal


@dataclass
class AssetInventorySummary:
    asset_id: str
    quantity: Decimal
    value: Decimal


@dataclass
class InventorySummary:
    as_of: datetime
    assets: list[AssetInventorySummary] = field(default_factory=list)


def compute_inventory_summary(
    owned_wallet_ids: set[str],
    *,
    wallet_balance_tracker: WalletBalanceTracker,
    price_provider: PriceProvider,
    as_of: datetime | None = None,
) -> InventorySummary:
    now = as_of or datetime.now(timezone.utc)

    summaries: list[AssetInventorySummary] = []

    for asset_id, quantity in sorted(
        wallet_balance_tracker.asset_balances_for(owned_wallet_ids).items(),
        key=lambda item: item[0],
    ):
        if quantity <= 0:
            continue
        rate = price_provider.rate(asset_id, InventoryEngine.EUR_ASSET_ID, now)
        summaries.append(
            AssetInventorySummary(
                asset_id=asset_id,
                quantity=quantity,
                value=quantity * rate,
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
        quantities_text = f"{format_decimal(asset.quantity)}"
        values_text = f"{format_currency(asset.value)}"
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
