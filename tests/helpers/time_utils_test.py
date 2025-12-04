from datetime import datetime, timezone
from decimal import Decimal
from random import Random

from domain.ledger import EventType, LedgerLeg, WalletId
from tests.constants import ETH
from tests.helpers.time_utils import TimeGenerator, make_event


def test_time_generator_increases_with_seed() -> None:
    rng = Random(42)
    gen = TimeGenerator(_rng=rng)

    ts1 = gen()
    ts2 = gen()
    ts3 = gen()

    assert ts1 < ts2 < ts3
    gaps = [(ts2 - ts1).total_seconds(), (ts3 - ts2).total_seconds()]
    for gap in gaps:
        assert 5 <= gap <= 60

    # Deterministic given the same seed
    gen_again = TimeGenerator(_rng=Random(42))
    ts1_b, ts2_b, ts3_b = gen_again(), gen_again(), gen_again()
    gaps_b = [(ts2_b - ts1_b).total_seconds(), (ts3_b - ts2_b).total_seconds()]
    assert gaps == gaps_b


def test_make_event_uses_generator_when_timestamp_missing() -> None:
    gen = TimeGenerator(_rng=Random(1))
    legs = [LedgerLeg(asset_id=ETH, quantity=Decimal("1"), wallet_id=WalletId("w"))]

    event1 = make_event(event_type=EventType.REWARD, legs=legs, ts_gen=gen)
    event2 = make_event(event_type=EventType.REWARD, legs=legs, ts_gen=gen)

    assert event1.timestamp < event2.timestamp
    assert event1.timestamp.tzinfo == timezone.utc


def test_make_event_respects_provided_timestamp() -> None:
    explicit_ts = datetime(2024, 2, 1, tzinfo=timezone.utc)
    legs = [LedgerLeg(asset_id=ETH, quantity=Decimal("1"), wallet_id=WalletId("w"))]

    event = make_event(event_type=EventType.REWARD, legs=legs, timestamp=explicit_ts)

    assert event.timestamp == explicit_ts


def test_make_event_uses_shared_generator_by_default() -> None:
    legs = [LedgerLeg(asset_id=ETH, quantity=Decimal("1"), wallet_id=WalletId("w"))]

    first = make_event(event_type=EventType.REWARD, legs=legs)
    second = make_event(event_type=EventType.REWARD, legs=legs)

    assert first.timestamp < second.timestamp


def test_default_generator_is_reset_between_tests() -> None:
    # After the autouse reset, we should start from the same baseline.
    legs = [LedgerLeg(asset_id=ETH, quantity=Decimal("1"), wallet_id=WalletId("w"))]

    first = make_event(event_type=EventType.REWARD, legs=legs)
    second = make_event(event_type=EventType.REWARD, legs=legs)

    assert first.timestamp < second.timestamp
