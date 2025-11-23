from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from domain.inventory import InventoryResult
from domain.ledger import LedgerEvent


def dump_inventory_debug(
    events: Iterable[LedgerEvent],
    inventory_result: InventoryResult,
    *,
    root_dir: Path = Path(".tmp/debug_dumps"),
) -> dict[str, Path]:
    """Persist ledger and inventory artifacts for debugging."""

    root_dir.mkdir(parents=True, exist_ok=True)
    dump_dir = root_dir / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dump_dir.mkdir(parents=True, exist_ok=False)

    events_path = dump_dir / "ledger_events.json"
    lots_path = dump_dir / "acquisition_lots.csv"
    disposals_path = dump_dir / "disposal_links.csv"

    events_payload = [event.model_dump(mode="json") for event in events]
    events_path.write_text(json.dumps(events_payload, indent=2), encoding="utf-8")

    with lots_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["id", "acquired_event_id", "acquired_leg_id", "cost_eur_per_unit"])
        for lot in inventory_result.acquisition_lots:
            writer.writerow(
                [
                    str(lot.id),
                    str(lot.acquired_event_id),
                    str(lot.acquired_leg_id),
                    str(lot.cost_eur_per_unit),
                ]
            )

    with disposals_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["id", "disposal_leg_id", "lot_id", "quantity_used", "proceeds_total_eur"])
        for link in inventory_result.disposal_links:
            writer.writerow(
                [
                    str(link.id),
                    str(link.disposal_leg_id),
                    str(link.lot_id),
                    str(link.quantity_used),
                    str(link.proceeds_total_eur),
                ]
            )

    return {
        "events": events_path,
        "acquisition_lots": lots_path,
        "disposal_links": disposals_path,
    }
