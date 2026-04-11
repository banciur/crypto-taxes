from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.acquisition_disposal import (
    AcquisitionDisposalProjection,
    AcquisitionDisposalProjectionError,
    AcquisitionDisposalProjector,
    AcquisitionLot,
    DisposalLink,
)
from domain.ledger import AssetId, EventLocation, EventOrigin, LedgerEvent, LedgerLeg
from tests.constants import BASE_WALLET, ETH, EUR

USDC = AssetId("USDC")
LP = AssetId("LP")
LP_A = AssetId("LP_A")
LP_B = AssetId("LP_B")
BONUS = AssetId("BONUS")
EXOTIC = AssetId("EXOTIC")
FEE_ASSET = AssetId("FEE_ASSET")

BASE_TIMESTAMP = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)


class FixedPriceProvider:
    def __init__(self, rates: dict[AssetId, Decimal]) -> None:
        self._rates = rates

    def rate(self, base_id: str, quote_id: str, timestamp: datetime) -> Decimal:
        _ = timestamp
        if quote_id != EUR:
            raise LookupError(f"Unsupported quote asset: {quote_id}")
        asset_id = AssetId(base_id)
        if asset_id not in self._rates:
            raise LookupError(f"Missing price for {asset_id}")
        return self._rates[asset_id]


def _projector(*, rates: dict[AssetId, Decimal]) -> AcquisitionDisposalProjector:
    return AcquisitionDisposalProjector(price_provider=FixedPriceProvider(rates))


def _event(*, external_id: str, offset_days: int, legs: list[LedgerLeg]) -> LedgerEvent:
    return LedgerEvent(
        timestamp=BASE_TIMESTAMP + timedelta(days=offset_days),
        event_origin=EventOrigin(location=EventLocation.INTERNAL, external_id=external_id),
        ingestion="test",
        legs=legs,
    )


def _leg(
    *,
    asset_id: AssetId,
    quantity: str,
    is_fee: bool = False,
) -> LedgerLeg:
    return LedgerLeg(
        asset_id=asset_id,
        quantity=Decimal(quantity),
        account_chain_id=BASE_WALLET,
        is_fee=is_fee,
    )


def _lot_for_event(
    projection: AcquisitionDisposalProjection,
    *,
    external_id: str,
    asset_id: AssetId,
    is_fee: bool = False,
) -> AcquisitionLot:
    return next(
        lot
        for lot in projection.acquisition_lots
        if lot.event_origin.external_id == external_id and lot.asset_id == asset_id and lot.is_fee is is_fee
    )


def _link_for_event(
    projection: AcquisitionDisposalProjection,
    *,
    external_id: str,
    asset_id: AssetId,
    is_fee: bool = False,
) -> DisposalLink:
    return next(
        link
        for link in projection.disposal_links
        if link.event_origin.external_id == external_id and link.asset_id == asset_id and link.is_fee is is_fee
    )


def test_direct_prices_without_exact_eur_do_not_force_balance() -> None:
    eth_quantity = Decimal("1")
    eth_cost_eur = Decimal("2000")
    usdc_quantity = Decimal("1800")
    eth_market_rate = Decimal("1500")
    usdc_market_rate = Decimal("0.95")

    projection = _projector(rates={ETH: eth_market_rate, USDC: usdc_market_rate}).project(
        [
            _event(
                external_id="buy-eth",
                offset_days=0,
                legs=[
                    _leg(asset_id=ETH, quantity=str(eth_quantity)),
                    _leg(asset_id=EUR, quantity=f"-{eth_cost_eur}"),
                ],
            ),
            _event(
                external_id="swap-eth-to-usdc",
                offset_days=1,
                legs=[
                    _leg(asset_id=ETH, quantity=f"-{eth_quantity}"),
                    _leg(asset_id=USDC, quantity=str(usdc_quantity)),
                ],
            ),
        ]
    )

    eth_link = _link_for_event(projection, external_id="swap-eth-to-usdc", asset_id=ETH)
    usdc_lot = _lot_for_event(projection, external_id="swap-eth-to-usdc", asset_id=USDC)

    assert eth_link.proceeds_total == eth_quantity * eth_market_rate
    assert usdc_lot.cost_per_unit == usdc_market_rate


def test_exact_eur_with_multiple_same_side_assets_respects_authoritative_total() -> None:
    eth_quantity = Decimal("1")
    exact_eur = Decimal("100")
    bonus_quantity = Decimal("1")
    bonus_market_rate = Decimal("20")

    projection = _projector(rates={ETH: Decimal("50"), BONUS: bonus_market_rate}).project(
        [
            _event(
                external_id="acquire-eth",
                offset_days=0,
                legs=[
                    _leg(asset_id=ETH, quantity=str(eth_quantity)),
                    _leg(asset_id=EUR, quantity="-40"),
                ],
            ),
            _event(
                external_id="dispose-eth-for-eur-and-bonus",
                offset_days=1,
                legs=[
                    _leg(asset_id=EUR, quantity=str(exact_eur)),
                    _leg(asset_id=BONUS, quantity=str(bonus_quantity)),
                    _leg(asset_id=ETH, quantity=f"-{eth_quantity}"),
                ],
            ),
        ]
    )

    eth_link = _link_for_event(projection, external_id="dispose-eth-for-eur-and-bonus", asset_id=ETH)
    bonus_lot = _lot_for_event(projection, external_id="dispose-eth-for-eur-and-bonus", asset_id=BONUS)

    assert bonus_lot.cost_per_unit == bonus_market_rate
    assert eth_link.proceeds_total == exact_eur + (bonus_quantity * bonus_market_rate)


def test_single_unpriceable_non_fee_asset_is_solved_by_remainder() -> None:
    eth_quantity = Decimal("1")
    eth_market_rate = Decimal("200")

    projection = _projector(rates={ETH: eth_market_rate}).project(
        [
            _event(
                external_id="acquire-eth",
                offset_days=0,
                legs=[
                    _leg(asset_id=ETH, quantity=str(eth_quantity)),
                    _leg(asset_id=EUR, quantity="-100"),
                ],
            ),
            _event(
                external_id="swap-eth-to-lp",
                offset_days=1,
                legs=[
                    _leg(asset_id=ETH, quantity=f"-{eth_quantity}"),
                    _leg(asset_id=LP, quantity="1"),
                ],
            ),
        ]
    )

    eth_link = _link_for_event(projection, external_id="swap-eth-to-lp", asset_id=ETH)
    lp_lot = _lot_for_event(projection, external_id="swap-eth-to-lp", asset_id=LP)

    assert eth_link.proceeds_total == eth_quantity * eth_market_rate
    assert lp_lot.cost_per_unit == eth_market_rate


def test_more_than_one_distinct_unpriceable_non_fee_asset_fails() -> None:
    projector = _projector(rates={ETH: Decimal("200")})

    with pytest.raises(AcquisitionDisposalProjectionError, match="distinct non-fee asset"):
        projector.project(
            [
                _event(
                    external_id="acquire-eth",
                    offset_days=0,
                    legs=[
                        _leg(asset_id=ETH, quantity="1"),
                        _leg(asset_id=EUR, quantity="-100"),
                    ],
                ),
                _event(
                    external_id="swap-eth-to-two-unknowns",
                    offset_days=1,
                    legs=[
                        _leg(asset_id=ETH, quantity="-1"),
                        _leg(asset_id=LP_A, quantity="1"),
                        _leg(asset_id=LP_B, quantity="1"),
                    ],
                ),
            ]
        )


def test_one_sided_event_requires_direct_price() -> None:
    projector = _projector(rates={})

    with pytest.raises(AcquisitionDisposalProjectionError, match="One-sided event"):
        projector.project(
            [
                _event(
                    external_id="reward-lp",
                    offset_days=0,
                    legs=[_leg(asset_id=LP, quantity="1")],
                )
            ]
        )


def test_fee_asset_is_excluded_from_non_fee_balancing_and_inherits_same_event_rate() -> None:
    non_fee_quantity = Decimal("10")
    fee_quantity = Decimal("1")
    usdc_quantity = Decimal("110")

    projection = _projector(rates={USDC: Decimal("1")}).project(
        [
            _event(
                external_id="acquire-exotic",
                offset_days=0,
                legs=[
                    _leg(asset_id=EXOTIC, quantity="11"),
                    _leg(asset_id=EUR, quantity="-110"),
                ],
            ),
            _event(
                external_id="swap-exotic-with-fee",
                offset_days=1,
                legs=[
                    _leg(asset_id=EXOTIC, quantity=f"-{non_fee_quantity}"),
                    _leg(asset_id=EXOTIC, quantity=f"-{fee_quantity}", is_fee=True),
                    _leg(asset_id=USDC, quantity=str(usdc_quantity)),
                ],
            ),
        ]
    )

    non_fee_link = _link_for_event(projection, external_id="swap-exotic-with-fee", asset_id=EXOTIC)
    fee_link = _link_for_event(projection, external_id="swap-exotic-with-fee", asset_id=EXOTIC, is_fee=True)

    assert non_fee_link.proceeds_total == usdc_quantity
    assert fee_link.proceeds_total == Decimal("11")


def test_fee_only_asset_falls_back_to_direct_price() -> None:
    fee_quantity = Decimal("0.01")
    fee_rate = Decimal("2000")

    projection = _projector(rates={USDC: Decimal("1"), FEE_ASSET: fee_rate}).project(
        [
            _event(
                external_id="acquire-fee-asset",
                offset_days=0,
                legs=[
                    _leg(asset_id=FEE_ASSET, quantity="1"),
                    _leg(asset_id=EUR, quantity="-100"),
                ],
            ),
            _event(
                external_id="reward-with-fee",
                offset_days=1,
                legs=[
                    _leg(asset_id=USDC, quantity="100"),
                    _leg(asset_id=FEE_ASSET, quantity=f"-{fee_quantity}", is_fee=True),
                ],
            ),
        ]
    )

    fee_link = _link_for_event(projection, external_id="reward-with-fee", asset_id=FEE_ASSET, is_fee=True)

    assert fee_link.proceeds_total == fee_quantity * fee_rate


def test_fee_only_asset_without_direct_price_fails() -> None:
    projector = _projector(rates={USDC: Decimal("1")})

    with pytest.raises(AcquisitionDisposalProjectionError, match="fee legs"):
        projector.project(
            [
                _event(
                    external_id="acquire-fee-asset",
                    offset_days=0,
                    legs=[
                        _leg(asset_id=FEE_ASSET, quantity="1"),
                        _leg(asset_id=EUR, quantity="-100"),
                    ],
                ),
                _event(
                    external_id="reward-with-fee",
                    offset_days=1,
                    legs=[
                        _leg(asset_id=USDC, quantity="100"),
                        _leg(asset_id=FEE_ASSET, quantity="-0.01", is_fee=True),
                    ],
                ),
            ]
        )


def test_negative_remainder_fails() -> None:
    projector = _projector(rates={ETH: Decimal("100"), BONUS: Decimal("200")})

    with pytest.raises(AcquisitionDisposalProjectionError, match="negative value"):
        projector.project(
            [
                _event(
                    external_id="acquire-eth",
                    offset_days=0,
                    legs=[
                        _leg(asset_id=ETH, quantity="1"),
                        _leg(asset_id=EUR, quantity="-100"),
                    ],
                ),
                _event(
                    external_id="unsupported-remainder",
                    offset_days=1,
                    legs=[
                        _leg(asset_id=ETH, quantity="-1"),
                        _leg(asset_id=BONUS, quantity="1"),
                        _leg(asset_id=LP, quantity="1"),
                    ],
                ),
            ]
        )
