from __future__ import annotations

from csv import DictWriter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from accounts import account_chain_id_for
from domain.ledger import EventLocation, WalletAddress
from importers.stakewise import StakewiseImporter

FIELDNAMES = [
    "Reward (ETH)",
    "Reward (USD)",
    "Date (YYYY-MM-DD)",
]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def test_importer_sets_stakewise_note_on_reward_events(tmp_path: Path) -> None:
    wallet_address = WalletAddress("0x6c1086c292a7e1fdf66c68776ea972038467a370")
    account_chain_id = account_chain_id_for(location=EventLocation.ETHEREUM, address=wallet_address)
    reward = Decimal("0.123456789012345678")
    file = tmp_path / "Stakewise.csv"
    write_csv(
        file,
        [
            {
                "Reward (ETH)": str(reward),
                "Reward (USD)": "1.23",
                "Date (YYYY-MM-DD)": "2024-12-29 12:27 UTC",
            }
        ],
    )

    event = StakewiseImporter([file], wallet_address=wallet_address).load_events()[0]

    assert event.timestamp == datetime(2024, 12, 29, 12, 27, tzinfo=timezone.utc)
    assert event.ingestion == "stakewise_rewards_csv"
    assert event.note == "staking - StakeWise"
    assert len(event.legs) == 1
    leg = event.legs[0]
    assert leg.asset_id == "ETH"
    assert leg.quantity == reward
    assert leg.account_chain_id == account_chain_id
