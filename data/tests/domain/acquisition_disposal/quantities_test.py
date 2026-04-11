from __future__ import annotations

from decimal import Decimal

from domain.acquisition_disposal.quantities import project_event_quantities
from tests.constants import ALT_BASE_WALLET, BASE_WALLET, ETH, EUR, LEDGER_WALLET
from tests.domain.acquisition_disposal.helpers import EXOTIC, USDC, make_event, make_leg


def test_internal_transfer_projects_no_non_fee_asset_group() -> None:
    quantity = Decimal("1")

    projected_event = project_event_quantities(
        make_event(
            legs=[
                make_leg(account_chain_id=BASE_WALLET, asset_id=ETH, quantity=quantity),
                make_leg(account_chain_id=ALT_BASE_WALLET, asset_id=ETH, quantity=-quantity),
            ],
        )
    )

    assert projected_event.non_fee_groups == []
    assert projected_event.fee_groups == []


def test_non_fee_eur_remains_in_non_fee_groups() -> None:
    acquisition_quantity = Decimal("1")
    eur_quantity = Decimal("-100")

    projected_event = project_event_quantities(
        make_event(
            legs=[
                make_leg(account_chain_id=BASE_WALLET, asset_id=ETH, quantity=acquisition_quantity),
                make_leg(account_chain_id=BASE_WALLET, asset_id=EUR, quantity=eur_quantity),
            ],
        )
    )

    eth_group = next(group for group in projected_event.non_fee_groups if group.asset_id == ETH)
    eur_group = next(group for group in projected_event.non_fee_groups if group.asset_id == EUR)

    assert {group.asset_id for group in projected_event.non_fee_groups} == {ETH, EUR}
    assert len(eth_group.legs) == 1
    assert eth_group.legs[0].quantity == acquisition_quantity
    assert len(eur_group.legs) == 1
    assert eur_group.legs[0].quantity == eur_quantity


def test_fee_group_stays_separate_when_fee_asset_matches_non_fee_asset() -> None:
    non_fee_quantity = Decimal("-10")
    fee_quantity = Decimal("-1")
    usdc_quantity = Decimal("110")

    projected_event = project_event_quantities(
        make_event(
            legs=[
                make_leg(account_chain_id=BASE_WALLET, asset_id=EXOTIC, quantity=non_fee_quantity),
                make_leg(account_chain_id=BASE_WALLET, asset_id=EXOTIC, quantity=fee_quantity, is_fee=True),
                make_leg(account_chain_id=BASE_WALLET, asset_id=USDC, quantity=usdc_quantity),
            ],
        )
    )

    exotic_group = next(group for group in projected_event.non_fee_groups if group.asset_id == EXOTIC)
    usdc_group = next(group for group in projected_event.non_fee_groups if group.asset_id == USDC)
    (fee_group,) = projected_event.fee_groups

    assert exotic_group.legs[0].quantity == non_fee_quantity
    assert usdc_group.legs[0].quantity == usdc_quantity
    assert fee_group.asset_id == EXOTIC
    assert fee_group.is_fee is True
    assert fee_group.legs[0].quantity == fee_quantity


def test_residual_quantity_is_split_across_multiple_same_sign_source_legs() -> None:
    negative_quantity = Decimal("-1")
    first_positive_quantity = Decimal("0.6")
    second_positive_quantity = Decimal("0.5")
    projected_total = first_positive_quantity + second_positive_quantity + negative_quantity

    projected_event = project_event_quantities(
        make_event(
            legs=[
                make_leg(account_chain_id=LEDGER_WALLET, asset_id=ETH, quantity=negative_quantity),
                make_leg(account_chain_id=BASE_WALLET, asset_id=ETH, quantity=first_positive_quantity),
                make_leg(account_chain_id=ALT_BASE_WALLET, asset_id=ETH, quantity=second_positive_quantity),
            ],
        )
    )

    (asset_group,) = projected_event.non_fee_groups

    assert asset_group.asset_id == ETH
    assert len(asset_group.legs) == 2
    assert {leg.account_chain_id for leg in asset_group.legs} == {BASE_WALLET, ALT_BASE_WALLET}
    assert all(leg.quantity > 0 for leg in asset_group.legs)
    assert sum((leg.quantity for leg in asset_group.legs), start=Decimal(0)) == projected_total
