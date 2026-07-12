from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from db.price_cache import PriceCacheRepository, init_price_cache_db
from domain.ledger import AssetId
from domain.pricing import PriceRecord, PriceSource
from services.price_resolver import PriceResolver
from services.price_service import PriceService
from tests.constants import BTC, ETH, EUR, USD, USDC

TS = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
EURC = AssetId("EURC")
RETH2 = AssetId("RETH2")  # configured in ASSETS_PRICED_AS as taking ETH's price


class _StubSource:
    """Source that answers a fixed set of ``base->quote`` legs and records every fetch."""

    def __init__(self, rates: dict[tuple[AssetId, AssetId], Decimal | None], *, source_name: str) -> None:
        self._rates = rates
        self.source_name = source_name
        self.calls: list[tuple[AssetId, AssetId, datetime]] = []

    def fetch_record(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord:
        self.calls.append((base_id, quote_id, timestamp))
        if (base_id, quote_id) not in self._rates:
            raise AssertionError(f"unexpected fetch {base_id}->{quote_id}")
        return PriceRecord(
            base_id=base_id,
            quote_id=quote_id,
            rate=self._rates[(base_id, quote_id)],
            source=self.source_name,
            valid_from=timestamp,
            valid_to=timestamp + timedelta(minutes=5),
            fetched_at=timestamp,
        )


def _store(tmp_path: Path) -> PriceCacheRepository:
    session = init_price_cache_db(db_path=tmp_path / "price_cache.db")
    return PriceCacheRepository(session)


def _service(*, crypto: PriceSource, fiat: PriceSource, store: PriceCacheRepository) -> PriceService:
    resolver = PriceResolver(crypto_source=crypto, fiat_source=fiat)
    return PriceService(resolver=resolver, cache=store)


def _empty_source(source_name: str) -> _StubSource:
    return _StubSource({}, source_name=source_name)


def test_pivot_composes_legs_through_numeraire(tmp_path: Path) -> None:
    crypto = _StubSource({(ETH, USD): Decimal("2000")}, source_name="crypto")
    fiat = _StubSource({(EUR, USD): Decimal("1.25")}, source_name="fiat")
    service = _service(crypto=crypto, fiat=fiat, store=_store(tmp_path))

    assert service.rate(ETH, EUR, TS) == Decimal("1600")
    assert crypto.calls == [(ETH, USD, TS)]
    assert fiat.calls == [(EUR, USD, TS)]


def test_pivot_caches_only_leg_edges(tmp_path: Path) -> None:
    crypto = _StubSource({(ETH, USD): Decimal("2000")}, source_name="crypto")
    fiat = _StubSource({(EUR, USD): Decimal("1.25")}, source_name="fiat")
    store = _store(tmp_path)
    service = _service(crypto=crypto, fiat=fiat, store=store)

    first = service.rate(ETH, EUR, TS)
    second = service.rate(ETH, EUR, TS)

    assert first == second == Decimal("1600")
    # Legs are served from cache on the second call; the composed cross-rate is never stored.
    assert crypto.calls == [(ETH, USD, TS)]
    assert fiat.calls == [(EUR, USD, TS)]
    assert store.read(ETH, EUR, TS) is None
    assert store.read(ETH, USD, TS) is not None
    assert store.read(EUR, USD, TS) is not None


def test_identity_pair_short_circuits(tmp_path: Path) -> None:
    crypto = _empty_source("crypto")
    fiat = _empty_source("fiat")
    store = _store(tmp_path)
    service = _service(crypto=crypto, fiat=fiat, store=store)

    assert service.rate(EUR, EUR, TS) == Decimal(1)
    assert crypto.calls == []
    assert fiat.calls == []
    assert store.read(EUR, EUR, TS) is None


def test_numeraire_quote_uses_single_leg(tmp_path: Path) -> None:
    crypto = _StubSource({(BTC, USD): Decimal("30000")}, source_name="crypto")
    fiat = _empty_source("fiat")
    service = _service(crypto=crypto, fiat=fiat, store=_store(tmp_path))

    assert service.rate(BTC, USD, TS) == Decimal("30000")
    assert crypto.calls == [(BTC, USD, TS)]
    assert fiat.calls == []


def test_direct_cached_edge_preferred_over_pivot(tmp_path: Path) -> None:
    crypto = _empty_source("crypto")
    fiat = _empty_source("fiat")
    store = _store(tmp_path)
    store.write(
        PriceRecord(
            base_id=ETH,
            quote_id=EUR,
            rate=Decimal("999"),
            source="manual",
            valid_from=TS - timedelta(days=1),
            valid_to=TS + timedelta(days=1),
            fetched_at=TS,
        )
    )
    service = _service(crypto=crypto, fiat=fiat, store=store)

    assert service.rate(ETH, EUR, TS) == Decimal("999")
    assert crypto.calls == []
    assert fiat.calls == []


def test_usd_pegged_stable_resolves_to_one_against_numeraire(tmp_path: Path) -> None:
    crypto = _empty_source("crypto")
    fiat = _StubSource({(EUR, USD): Decimal("1.25")}, source_name="fiat")
    service = _service(crypto=crypto, fiat=fiat, store=_store(tmp_path))

    # USDC pegs to the numeraire (USD), so its leg is a synthetic 1; only the EUR leg fetches.
    assert service.rate(USDC, EUR, TS) == Decimal("0.8")
    assert service.rate(USDC, USD, TS) == Decimal(1)
    assert crypto.calls == []


def test_eur_pegged_stable_resolves_through_peg_currency(tmp_path: Path) -> None:
    crypto = _empty_source("crypto")
    fiat = _StubSource({(EUR, USD): Decimal("1.25")}, source_name="fiat")
    service = _service(crypto=crypto, fiat=fiat, store=_store(tmp_path))

    # EURC pegs to EUR, not the numeraire: EURC->USD must equal EUR->USD, not 1.
    assert service.rate(EURC, USD, TS) == Decimal("1.25")
    # And EURC->EUR is 1, since a EUR-pegged stable is worth one EUR.
    assert service.rate(EURC, EUR, TS) == Decimal(1)
    # EURC is never priced as a crypto asset; only the shared EUR->USD leg is fetched.
    assert crypto.calls == []
    assert fiat.calls == [(EUR, USD, TS)]


def test_unpriceable_leg_returns_none_and_negative_caches(tmp_path: Path) -> None:
    crypto = _StubSource({(BTC, USD): Decimal("30000")}, source_name="crypto")
    fiat = _StubSource({(EUR, USD): None}, source_name="fiat")
    store = _store(tmp_path)
    service = _service(crypto=crypto, fiat=fiat, store=store)

    assert service.rate(BTC, EUR, TS) is None
    negative = store.read(EUR, USD, TS)
    assert negative is not None
    assert negative.rate is None
    assert negative.source == "fiat"

    # The negative EUR leg is cached; a second resolution does not re-fetch either leg.
    assert service.rate(BTC, EUR, TS) is None
    assert crypto.calls == [(BTC, USD, TS)]
    assert fiat.calls == [(EUR, USD, TS)]


def test_operational_error_propagates_without_caching(tmp_path: Path) -> None:
    class _RaisingSource:
        source_name = "crypto"

        def fetch_record(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord:
            _ = base_id, quote_id, timestamp
            raise RuntimeError("backend down")

    fiat = _StubSource({(EUR, USD): Decimal("1.25")}, source_name="fiat")
    store = _store(tmp_path)
    service = _service(crypto=_RaisingSource(), fiat=fiat, store=store)

    with pytest.raises(RuntimeError, match="backend down"):
        service.rate(ETH, EUR, TS)
    assert store.read(ETH, USD, TS) is None


def test_asset_priced_as_another_borrows_that_asset_rate(tmp_path: Path) -> None:
    eth_usd = Decimal("2000")
    eur_usd = Decimal("1.25")
    crypto = _StubSource({(ETH, USD): eth_usd}, source_name="crypto")
    fiat = _StubSource({(EUR, USD): eur_usd}, source_name="fiat")
    store = _store(tmp_path)
    service = _service(crypto=crypto, fiat=fiat, store=store)

    assert service.rate(RETH2, EUR, TS) == eth_usd / eur_usd
    # RETH2 never reaches the source or the cache; only the substituted ETH leg does.
    assert crypto.calls == [(ETH, USD, TS)]
    assert store.read(RETH2, USD, TS) is None


def test_asset_priced_as_another_is_one_to_one_against_it(tmp_path: Path) -> None:
    crypto = _empty_source("crypto")
    fiat = _empty_source("fiat")
    service = _service(crypto=crypto, fiat=fiat, store=_store(tmp_path))

    # Both sides substitute to ETH, so the identity short-circuit answers without any lookup.
    assert service.rate(RETH2, ETH, TS) == Decimal(1)
    assert crypto.calls == []


def test_asset_priced_as_another_ignores_its_own_cached_edge(tmp_path: Path) -> None:
    eth_usd = Decimal("2000")
    crypto = _StubSource({(ETH, USD): eth_usd}, source_name="crypto")
    fiat = _empty_source("fiat")
    store = _store(tmp_path)
    store.write(
        PriceRecord(
            base_id=RETH2,
            quote_id=USD,
            rate=None,
            source="crypto",
            valid_from=TS - timedelta(days=1),
            valid_to=TS + timedelta(days=1),
            fetched_at=TS,
        )
    )
    service = _service(crypto=crypto, fiat=fiat, store=store)

    # Substitution happens above the cache, so a stale RETH2 edge cannot make it unpriceable.
    assert service.rate(RETH2, USD, TS) == eth_usd


def test_service_defaults_timestamp_and_normalizes_case(tmp_path: Path) -> None:
    crypto = _StubSource({(BTC, USD): Decimal("30000")}, source_name="crypto")
    fiat = _empty_source("fiat")
    service = _service(crypto=crypto, fiat=fiat, store=_store(tmp_path))

    assert service.rate(AssetId("btc"), AssetId("usd")) == Decimal("30000")
    assert len(crypto.calls) == 1
    assert crypto.calls[0][0] == BTC
    assert crypto.calls[0][1] == USD
