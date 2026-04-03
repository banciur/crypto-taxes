from __future__ import annotations

from csv import DictWriter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from accounts import account_chain_id_for
from domain.ledger import EventLocation, WalletAddress
from importers.lido import LidoImporter

FIELDNAMES = [
    "date",
    "type",
    "direction",
    "change",
    "change_wei",
    "change_USD",
    "apr",
    "balance",
    "balance_wei",
]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def lido_row(
    *,
    date: str,
    row_type: str,
    change: str,
    change_wei: str,
    direction: str = "",
    change_usd: str = "0",
    apr: str = "",
    balance: str = "0",
    balance_wei: str = "0",
) -> dict[str, str]:
    return {
        "date": date,
        "type": row_type,
        "direction": direction,
        "change": change,
        "change_wei": change_wei,
        "change_USD": change_usd,
        "apr": apr,
        "balance": balance,
        "balance_wei": balance_wei,
    }


def test_importer_ignores_non_reward_rows_and_sorts_rewards(tmp_path: Path) -> None:
    older_reward_ts = "2024-12-28T12:27:23.000Z"
    newer_reward_ts = "2024-12-29T12:27:35.000Z"
    older_reward_atomic = "684917007630447"
    newer_reward_atomic = "680345284314096"
    wallet_address = WalletAddress("0x6c1086c292a7e1fdf66c68776ea972038467a370")
    file = tmp_path / "lido.csv"
    write_csv(
        file,
        [
            lido_row(
                date=newer_reward_ts,
                row_type="reward",
                change="0.000680345284314096",
                change_wei=newer_reward_atomic,
            ),
            lido_row(
                date="2024-12-30T07:04:35.000Z",
                row_type="transfer",
                direction="out",
                change="9.056986181391699076",
                change_wei="9056986181391699076",
            ),
            lido_row(
                date=older_reward_ts,
                row_type="reward",
                change="0.000684917007630447",
                change_wei=older_reward_atomic,
            ),
            lido_row(
                date="2024-12-31T12:00:00.000Z",
                row_type="staking",
                change="0",
                change_wei="0",
            ),
        ],
    )

    events = LidoImporter(file, wallet_address=wallet_address).load_events()

    assert len(events) == 2
    assert [event.timestamp for event in events] == [
        datetime(2024, 12, 28, 12, 27, 23, tzinfo=timezone.utc),
        datetime(2024, 12, 29, 12, 27, 35, tzinfo=timezone.utc),
    ]
    assert [event.event_origin.external_id for event in events] == [
        "reward:2024-12-28T12:27:23+00:00",
        "reward:2024-12-29T12:27:35+00:00",
    ]


def test_importer_uses_change_wei_for_steth_quantity_and_sets_note(tmp_path: Path) -> None:
    reward_ts = "2024-12-29T12:27:35.000Z"
    reward_atomic = "680345284314096"
    reward_change = "999.999999999999999999"
    wallet_address = WalletAddress("0x6c1086c292a7e1fdf66c68776ea972038467a370")
    account_chain_id = account_chain_id_for(location=EventLocation.ETHEREUM, address=wallet_address)
    file = tmp_path / "lido.csv"
    write_csv(
        file,
        [
            lido_row(
                date=reward_ts,
                row_type="reward",
                change=reward_change,
                change_wei=reward_atomic,
            )
        ],
    )

    event = LidoImporter(file, wallet_address=wallet_address).load_events()[0]
    expected_quantity = Decimal(reward_atomic) / (Decimal(10) ** 18)

    assert event.event_origin.location == EventLocation.ETHEREUM
    assert event.event_origin.external_id == "reward:2024-12-29T12:27:35+00:00"
    assert event.ingestion == "lido_rewards_csv"
    assert event.note == "staking - Lido"
    assert len(event.legs) == 1
    leg = event.legs[0]
    assert leg.asset_id == "stETH"
    assert leg.quantity == expected_quantity
    assert leg.account_chain_id == account_chain_id
