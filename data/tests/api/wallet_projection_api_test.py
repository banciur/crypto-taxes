from fastapi.testclient import TestClient

from domain.wallet_projection import WalletTrackingState


def test_get_wallet_tracking_returns_not_run_when_state_is_missing(client: TestClient) -> None:
    response = client.get("/wallet-projection")
    expected = WalletTrackingState.not_run()

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
