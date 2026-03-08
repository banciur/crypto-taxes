from __future__ import annotations

import logging
from datetime import date
from time import sleep
from typing import Any, Mapping

from moralis import evm_api
from moralis.evm_api.wallets.get_wallet_history import Params
from openapi_evm_api.model.chain_list import ChainList

from domain.ledger import EventLocation, WalletAddress
from type_defs import RawTxs

logger = logging.getLogger(__name__)

_MORALIS_CHAIN_VALUES: dict[EventLocation, str] = {
    EventLocation.ETHEREUM: "eth",
    EventLocation.ARBITRUM: "arbitrum",
    EventLocation.BASE: "base",
    EventLocation.OPTIMISM: "optimism",
}


def _moralis_chain(location: EventLocation) -> ChainList:
    return ChainList(_MORALIS_CHAIN_VALUES[location])


class MoralisClient:
    # https://docs.moralis.com/
    def __init__(self, api_key: str, delay_seconds: float = 1.0):
        self.api_key = api_key
        self.delay_seconds = delay_seconds

    def fetch_transactions(
        self,
        location: EventLocation,
        address: WalletAddress,
        from_date: date | None = None,
    ) -> RawTxs:
        cursor: str | None = ""
        aggregated: list[Mapping[str, Any]] = []
        total = 0

        logger.info(
            "Fetching transactions location=%s address=%s%s",
            location,
            address,
            f" from_date={from_date:%Y-%m-%d}" if from_date else "",
        )

        while cursor is not None:
            params: Params = {"chain": _moralis_chain(location), "address": address}
            if from_date:
                params["from_date"] = from_date.strftime("%Y-%m-%d")
            if cursor:
                params["cursor"] = cursor

            sleep(self.delay_seconds)
            response = evm_api.wallets.get_wallet_history(
                api_key=self.api_key,
                params=params,
            )
            cursor = response.get("cursor")
            batch = response.get("result") or []

            aggregated.extend(batch)
            total += len(batch)

            logger.info(
                "Fetched batch size=%d total=%d location=%s address=%s",
                len(batch),
                total,
                location,
                address,
            )

        return aggregated
