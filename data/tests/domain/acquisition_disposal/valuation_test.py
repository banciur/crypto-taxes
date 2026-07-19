from datetime import datetime
from decimal import Decimal

import pytest

from domain.acquisition_disposal.errors import AcquisitionDisposalProjectionError, AcquisitionDisposalValuationError
from domain.acquisition_disposal.quantities import project_event_quantities
from domain.acquisition_disposal.valuation import _DirectRateResolver, _value_fee_groups, _value_non_fee_groups
from domain.ledger import AssetId, LedgerEvent
from domain.pricing import PriceProvider
from tests.constants import ETH, EUR, USD, USDC
from tests.domain.acquisition_disposal.helpers import EXOTIC, make_event
from tests.helpers.ledger import make_leg

USDT = AssetId("USDT")
LP = AssetId("LP")
LP_A = AssetId("LP_A")
LP_B = AssetId("LP_B")
BONUS = AssetId("BONUS")
FEE_ASSET = AssetId("FEE_ASSET")
DEBT = AssetId("DEBT")


class FixedPriceProvider(PriceProvider):
    def __init__(self, rates: dict[AssetId, Decimal]) -> None:
        self._rates = rates

    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal | None:
        _ = timestamp
        if base_id == quote_id:
            return Decimal(1)
        if quote_id != EUR:
            raise LookupError(f"Unsupported quote asset: {quote_id}")
        return self._rates.get(base_id)


def _rates_for(
    event: LedgerEvent,
    *,
    rates: dict[AssetId, Decimal],
    overrides: dict[AssetId, Decimal] | None = None,
) -> dict[AssetId, Decimal]:
    projected_event = project_event_quantities(event)
    rate_resolver = _DirectRateResolver(
        price_provider=FixedPriceProvider(rates),
        overrides_by_event_origin={event.event_origin: overrides or {}},
    )
    non_fee_rates = _value_non_fee_groups(
        projected_event,
        event_origin=event.event_origin,
        timestamp=event.timestamp,
        rate_resolver=rate_resolver,
        borrowed_rates={},
    )
    fee_rates = _value_fee_groups(
        projected_event.fee_groups,
        non_fee_prices=non_fee_rates,
        event_origin=event.event_origin,
        timestamp=event.timestamp,
        rate_resolver=rate_resolver,
    )
    return non_fee_rates | fee_rates


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


def test_liability_leg_cancels_its_underlying_on_the_same_side_without_rebalancing() -> None:
    # A borrow receives the asset and mints a debt token priced at the negative of that asset, so the
    # two acquisition legs cancel to zero EUR and every rate passes through untouched.
    borrow_quantity = Decimal("0.5")
    underlying_rate = Decimal("2500")

    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=ETH, quantity=borrow_quantity),
                make_leg(asset_id=DEBT, quantity=borrow_quantity),
            ],
        ),
        rates={ETH: underlying_rate, DEBT: -underlying_rate},
    )

    assert rates == {ETH: underlying_rate, DEBT: -underlying_rate}


def test_liability_leg_in_a_two_sided_event_is_rejected() -> None:
    # A liability rate that does not cancel within its side would corrupt tier rebalancing, so the
    # event is failed for manual correction instead.
    with pytest.raises(AcquisitionDisposalValuationError, match="Liability-rated"):
        _rates_for(
            make_event(
                legs=[
                    make_leg(asset_id=ETH, quantity=Decimal("-1")),
                    make_leg(asset_id=DEBT, quantity=Decimal("1")),
                ],
            ),
            rates={ETH: Decimal("1500"), DEBT: Decimal("-500")},
        )


def test_liability_leg_alongside_an_unpriceable_asset_is_rejected() -> None:
    # A single unpriceable asset would normally be remainder-solved, but a liability rate on the
    # other side breaks that solve's positive-magnitude assumption, so it is rejected.
    with pytest.raises(AcquisitionDisposalValuationError, match="Liability-rated"):
        _rates_for(
            make_event(
                legs=[
                    make_leg(asset_id=DEBT, quantity=Decimal("1")),
                    make_leg(asset_id=EXOTIC, quantity=Decimal("-1")),
                ],
            ),
            rates={DEBT: Decimal("-500")},
        )


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

    with pytest.raises(AcquisitionDisposalProjectionError, match="distinct non-fee asset") as exc_info:
        _rates_for(event, rates={ETH: Decimal("200")})

    assert f"assets={LP_A},{LP_B}" in str(exc_info.value)


def test_unpriceable_reference_priced_asset_fails_instead_of_being_remainder_solved() -> None:
    eth_quantity = Decimal("-1")
    usdc_quantity = Decimal("200")
    event = make_event(
        legs=[
            make_leg(asset_id=ETH, quantity=eth_quantity),
            make_leg(asset_id=USDC, quantity=usdc_quantity),
        ],
    )

    with pytest.raises(AcquisitionDisposalProjectionError, match="Reference-priced asset"):
        _rates_for(event, rates={ETH: Decimal("200")})


def test_one_sided_event_requires_direct_price() -> None:
    lp_quantity = Decimal("1")
    lp_asset = LP
    event = make_event(
        legs=[make_leg(asset_id=lp_asset, quantity=lp_quantity)],
    )

    with pytest.raises(AcquisitionDisposalProjectionError, match="One-sided event") as exc_info:
        _rates_for(event, rates={})

    assert f"asset={lp_asset}" in str(exc_info.value)
    assert isinstance(exc_info.value, AcquisitionDisposalValuationError)


def test_stable_yields_to_base_currency_when_peg_rate_disagrees() -> None:
    # Buying a stable for EUR: the EUR spent is what the stable cost, whatever the peg-derived rate says.
    eur_quantity = Decimal("-172.26")
    usdc_quantity = Decimal("200")
    usdc_peg_rate = Decimal("0.860956")
    expected_usdc_rate = abs(eur_quantity) / usdc_quantity

    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=EUR, quantity=eur_quantity),
                make_leg(asset_id=USDC, quantity=usdc_quantity),
            ],
        ),
        rates={USDC: usdc_peg_rate},
    )

    assert rates == {EUR: Decimal("1"), USDC: expected_usdc_rate}


def test_fiat_yields_to_base_currency() -> None:
    eur_quantity = Decimal("-100")
    usd_quantity = Decimal("125")
    usd_fx_rate = Decimal("0.85")
    expected_usd_rate = abs(eur_quantity) / usd_quantity

    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=EUR, quantity=eur_quantity),
                make_leg(asset_id=USD, quantity=usd_quantity),
            ],
        ),
        rates={USD: usd_fx_rate},
    )

    assert rates == {EUR: Decimal("1"), USD: expected_usd_rate}


def test_only_the_weakest_tier_absorbs_the_discrepancy() -> None:
    # EUR and USDC both outrank ETH, so USDC keeps its own rate and ETH absorbs the whole gap on its own.
    eur_quantity = Decimal("-1000")
    usdc_quantity = Decimal("400")
    eth_quantity = Decimal("0.5")
    usdc_rate = Decimal("0.9")
    eth_rate = Decimal("1000")
    expected_eth_rate = (abs(eur_quantity) - usdc_quantity * usdc_rate) / eth_quantity

    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=EUR, quantity=eur_quantity),
                make_leg(asset_id=USDC, quantity=usdc_quantity),
                make_leg(asset_id=ETH, quantity=eth_quantity),
            ],
        ),
        rates={USDC: usdc_rate, ETH: eth_rate},
    )

    assert rates == {EUR: Decimal("1"), USDC: usdc_rate, ETH: expected_eth_rate}


def test_same_tier_stables_move_toward_midpoint() -> None:
    usdc_quantity = Decimal("-100")
    usdt_quantity = Decimal("100")
    usdc_rate = Decimal("1")
    usdt_rate = Decimal("0.98")
    expected_midpoint_total = (abs(usdc_quantity) * usdc_rate + usdt_quantity * usdt_rate) / Decimal(2)

    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=USDC, quantity=usdc_quantity),
                make_leg(asset_id=USDT, quantity=usdt_quantity),
            ],
        ),
        rates={USDC: usdc_rate, USDT: usdt_rate},
    )

    assert rates == {
        USDC: expected_midpoint_total / abs(usdc_quantity),
        USDT: expected_midpoint_total / usdt_quantity,
    }


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


def test_override_supplies_price_for_otherwise_unpriceable_asset() -> None:
    # Provider has no price for LP; the override supplies it and the one-sided event values.
    lp_override_rate = Decimal("42")
    event = make_event(legs=[make_leg(asset_id=LP, quantity=Decimal("1"))])

    rates = _rates_for(event, rates={}, overrides={LP: lp_override_rate})

    assert rates == {LP: lp_override_rate}


def test_override_prices_a_fee_only_asset() -> None:
    # Without the override this raises (see test_fee_only_asset_without_direct_price_fails).
    usdc_rate = Decimal("1")
    fee_override_rate = Decimal("2000")
    event = make_event(
        legs=[
            make_leg(asset_id=USDC, quantity=Decimal("100")),
            make_leg(asset_id=FEE_ASSET, quantity=Decimal("-0.01"), is_fee=True),
        ],
    )

    rates = _rates_for(event, rates={USDC: usdc_rate}, overrides={FEE_ASSET: fee_override_rate})

    assert rates == {USDC: usdc_rate, FEE_ASSET: fee_override_rate}


def test_override_rate_participates_in_midpoint_rebalancing() -> None:
    eth_quantity = Decimal("-1")
    bonus_quantity = Decimal("1")
    eth_override_rate = Decimal("1500")
    bonus_rate = Decimal("1800")
    expected_midpoint_rate = (eth_override_rate + bonus_rate) / Decimal(2)

    # ETH is supplied only by the override, BONUS only by the provider; both are known and rebalance.
    rates = _rates_for(
        make_event(
            legs=[
                make_leg(asset_id=ETH, quantity=eth_quantity),
                make_leg(asset_id=BONUS, quantity=bonus_quantity),
            ],
        ),
        rates={BONUS: bonus_rate},
        overrides={ETH: eth_override_rate},
    )

    assert rates == {ETH: expected_midpoint_rate, BONUS: expected_midpoint_rate}


def test_override_rate_feeds_remainder_solving() -> None:
    # ETH known via override, LP unpriceable: LP is solved by remainder against the override rate.
    eth_override_rate = Decimal("200")
    event = make_event(
        legs=[
            make_leg(asset_id=ETH, quantity=Decimal("-1")),
            make_leg(asset_id=LP, quantity=Decimal("1")),
        ],
    )

    rates = _rates_for(event, rates={}, overrides={ETH: eth_override_rate})

    assert rates == {ETH: eth_override_rate, LP: eth_override_rate}


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
