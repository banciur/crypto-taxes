from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from domain.acquisition_disposal import AcquisitionDisposalProjectionError
from domain.acquisition_disposal.quantities import project_event_quantities
from domain.acquisition_disposal.valuation import value_projected_event
from domain.ledger import AssetId, LedgerEvent
from domain.pricing import PriceProvider
from tests.constants import ETH, EUR, USDC
from tests.domain.acquisition_disposal.helpers import EXOTIC, make_event
from tests.helpers.ledger import make_leg

LP = AssetId("LP")
LP_A = AssetId("LP_A")
LP_B = AssetId("LP_B")
BONUS = AssetId("BONUS")
FEE_ASSET = AssetId("FEE_ASSET")


class FixedPriceProvider(PriceProvider):
    def __init__(self, rates: dict[AssetId, Decimal]) -> None:
        self._rates = rates

    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal:
        _ = timestamp
        if quote_id != EUR:
            raise LookupError(f"Unsupported quote asset: {quote_id}")
        if base_id not in self._rates:
            raise LookupError(f"Missing price for {base_id}")
        return self._rates[base_id]


def _rates_for(event: LedgerEvent, *, rates: dict[AssetId, Decimal]) -> dict[AssetId, Decimal]:
    return value_projected_event(
        project_event_quantities(event),
        timestamp=event.timestamp,
        price_provider=FixedPriceProvider(rates),
    )


def test_anchor_asset_stays_fixed_while_adjustable_side_scales() -> None:
    eth_quantity = Decimal("-1")
    usdc_quantity = Decimal("1800")
    eth_rate = Decimal("1500")
    usdc_rate = Decimal("0.95")
    expected_eth_rate = usdc_quantity * usdc_rate / abs(eth_quantity)

    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=ETH, quantity=eth_quantity),
                make_leg(asset_id=USDC, quantity=usdc_quantity),
            ],
        ),
        rates={ETH: eth_rate, USDC: usdc_rate},
    )

    assert rates == {ETH: expected_eth_rate, USDC: usdc_rate}


def test_adjustable_assets_on_both_sides_move_toward_midpoint() -> None:
    eth_quantity = Decimal("-1")
    bonus_quantity = Decimal("1")
    eth_rate = Decimal("1500")
    bonus_rate = Decimal("1800")
    expected_midpoint_rate = (eth_rate + bonus_rate) / Decimal(2)

    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=ETH, quantity=eth_quantity),
                make_leg(asset_id=BONUS, quantity=bonus_quantity),
            ],
        ),
        rates={ETH: eth_rate, BONUS: bonus_rate},
    )

    assert rates == {ETH: expected_midpoint_rate, BONUS: expected_midpoint_rate}


def test_eur_anchor_uses_intrinsic_rate_and_crypto_side_scales_to_match() -> None:
    eur_quantity = Decimal("100")
    eth_quantity = Decimal("-1")
    eth_rate = Decimal("50")
    expected_eth_rate = eur_quantity / abs(eth_quantity)

    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=EUR, quantity=eur_quantity),
                make_leg(asset_id=ETH, quantity=eth_quantity),
            ],
        ),
        rates={ETH: eth_rate},
    )

    assert rates == {EUR: Decimal("1"), ETH: expected_eth_rate}


def test_single_unpriceable_non_fee_asset_is_solved_by_remainder() -> None:
    eth_quantity = Decimal("-1")
    lp_quantity = Decimal("1")
    eth_rate = Decimal("200")

    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=ETH, quantity=eth_quantity),
                make_leg(asset_id=LP, quantity=lp_quantity),
            ],
        ),
        rates={ETH: eth_rate},
    )

    assert rates == {ETH: eth_rate, LP: eth_rate}


def test_more_than_one_distinct_unpriceable_non_fee_asset_fails() -> None:
    eth_quantity = Decimal("-1")
    lp_a_quantity = Decimal("1")
    lp_b_quantity = Decimal("1")
    event = make_event(
        legs=[
            make_leg(asset_id=ETH, quantity=eth_quantity),
            make_leg(asset_id=LP_A, quantity=lp_a_quantity),
            make_leg(asset_id=LP_B, quantity=lp_b_quantity),
        ],
    )

    with pytest.raises(AcquisitionDisposalProjectionError, match="distinct non-fee asset"):
        _rates_for(event, rates={ETH: Decimal("200")})


def test_one_sided_event_requires_direct_price() -> None:
    lp_quantity = Decimal("1")
    event = make_event(
        legs=[make_leg(asset_id=LP, quantity=lp_quantity)],
    )

    with pytest.raises(AcquisitionDisposalProjectionError, match="One-sided event"):
        _rates_for(event, rates={})


def test_fully_anchored_mismatch_fails() -> None:
    eur_quantity = Decimal("100")
    usdc_quantity = Decimal("-90")

    event = make_event(
        legs=[
            make_leg(asset_id=EUR, quantity=eur_quantity),
            make_leg(asset_id=USDC, quantity=usdc_quantity),
        ],
    )

    with pytest.raises(AcquisitionDisposalProjectionError, match="fully anchored"):
        _rates_for(event, rates={USDC: Decimal("1")})


def test_fee_asset_is_excluded_from_non_fee_balancing_and_inherits_same_event_rate() -> None:
    non_fee_quantity = Decimal("10")
    fee_quantity = Decimal("1")
    usdc_quantity = Decimal("110")
    expected_exotic_rate = usdc_quantity / non_fee_quantity

    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=EXOTIC, quantity=-non_fee_quantity),
                make_leg(asset_id=EXOTIC, quantity=-fee_quantity, is_fee=True),
                make_leg(asset_id=USDC, quantity=usdc_quantity),
            ],
        ),
        rates={USDC: Decimal("1")},
    )

    assert rates == {EXOTIC: expected_exotic_rate, USDC: Decimal("1")}


def test_fee_only_asset_falls_back_to_direct_price() -> None:
    usdc_quantity = Decimal("100")
    fee_quantity = Decimal("-0.01")
    fee_rate = Decimal("2000")

    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=USDC, quantity=usdc_quantity),
                make_leg(asset_id=FEE_ASSET, quantity=fee_quantity, is_fee=True),
            ],
        ),
        rates={USDC: Decimal("1"), FEE_ASSET: fee_rate},
    )

    assert rates == {USDC: Decimal("1"), FEE_ASSET: fee_rate}


def test_fee_only_asset_without_direct_price_fails() -> None:
    usdc_quantity = Decimal("100")
    fee_quantity = Decimal("-0.01")
    event = make_event(
        legs=[
            make_leg(asset_id=USDC, quantity=usdc_quantity),
            make_leg(asset_id=FEE_ASSET, quantity=fee_quantity, is_fee=True),
        ],
    )

    with pytest.raises(AcquisitionDisposalProjectionError, match="fee legs"):
        _rates_for(event, rates={USDC: Decimal("1")})


def test_negative_remainder_fails() -> None:
    eth_quantity = Decimal("-1")
    bonus_quantity = Decimal("1")
    lp_quantity = Decimal("1")
    event = make_event(
        legs=[
            make_leg(asset_id=ETH, quantity=eth_quantity),
            make_leg(asset_id=BONUS, quantity=bonus_quantity),
            make_leg(asset_id=LP, quantity=lp_quantity),
        ],
    )

    with pytest.raises(AcquisitionDisposalProjectionError, match="negative value"):
        _rates_for(event, rates={ETH: Decimal("100"), BONUS: Decimal("200")})
