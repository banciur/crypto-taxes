import pytest

from domain.wallet_tracking import WalletProjector



@pytest.fixture(scope="function")
def wallet_projector() -> WalletProjector:
    return WalletProjector()
