import pytest
import httpx
from backend.app.paypal.client import PayPalClient, PayPalError


@pytest.mark.asyncio
async def test_paypal_client_refuses_production_url():
    with pytest.raises(PayPalError) as exc_info:
        PayPalClient(base_url="https://api-m.paypal.com")
    assert "SAFETY VIOLATION" in str(exc_info.value)
    assert "Only Sandbox URL" in str(exc_info.value)


@pytest.mark.asyncio
async def test_paypal_token_caching(monkeypatch):
    client = PayPalClient(client_id="test_id", client_secret="test_secret")

    call_count = 0

    class MockResponse:
        status_code = 200
        text = '{"access_token": "mocked_token_xyz", "expires_in": 3600}'
        def json(self):
            return {"access_token": "mocked_token_xyz", "expires_in": 3600}

    async def mock_post(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    token1 = await client._get_access_token()
    token2 = await client._get_access_token()

    assert token1 == "mocked_token_xyz"
    assert token2 == "mocked_token_xyz"
    # Token should be cached; only 1 network call made
    assert call_count == 1


@pytest.mark.asyncio
async def test_send_invoice_reminder_mock(monkeypatch):
    client = PayPalClient(client_id="test_id", client_secret="test_secret")
    client._access_token = "mocked_token"
    client._token_expires_at = 9999999999

    recorded_requests = []

    async def mock_request(self, method, url, **kwargs):
        recorded_requests.append((method, str(url), kwargs.get("json")))
        class MockResp:
            status_code = 204
            text = ""
        return MockResp()

    monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

    res = await client.send_invoice_reminder("INV2-12345", subject="Urgent reminder", note="Please pay promptly.")
    assert len(recorded_requests) == 1
    method, url, json_payload = recorded_requests[0]
    assert method == "POST"
    assert "INV2-12345/remind" in url
    assert json_payload["subject"] == "Urgent reminder"
    assert json_payload["send_to_recipient"] is True


@pytest.mark.asyncio
async def test_create_payout_with_idempotency(monkeypatch):
    client = PayPalClient(client_id="test_id", client_secret="test_secret")
    client._access_token = "mocked_token"
    client._token_expires_at = 9999999999

    recorded_payload = None

    async def mock_request(self, method, url, **kwargs):
        nonlocal recorded_payload
        recorded_payload = kwargs.get("json")
        class MockResp:
            status_code = 201
            text = '{"batch_header": {"payout_batch_id": "BATCH-999"}}'
            def json(self):
                return {"batch_header": {"payout_batch_id": "BATCH-999"}}
        return MockResp()

    monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

    res = await client.create_payout(
        recipient_email="contractor@example.com",
        amount=1600.0,
        currency="USD",
        sender_batch_id="batch_idem_12345",
        note="Contractor Installment 1"
    )
    assert res["batch_header"]["payout_batch_id"] == "BATCH-999"
    assert recorded_payload["sender_batch_header"]["sender_batch_id"] == "batch_idem_12345"
    assert recorded_payload["items"][0]["amount"]["value"] == "1600.00"
    assert recorded_payload["items"][0]["receiver"] == "contractor@example.com"


@pytest.mark.asyncio
async def test_verify_webhook_signature_success(monkeypatch):
    client = PayPalClient(client_id="test_id", client_secret="test_secret")
    client._access_token = "mocked_token"
    client._token_expires_at = 9999999999

    async def mock_request(self, method, url, **kwargs):
        class MockResp:
            status_code = 200
            text = '{"verification_status": "SUCCESS"}'
            def json(self):
                return {"verification_status": "SUCCESS"}
        return MockResp()

    monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

    verified = await client.verify_webhook_signature(
        transmission_id="trans_1",
        transmission_time="2026-11-06T12:00:00Z",
        cert_url="https://api.sandbox.paypal.com/cert.pem",
        auth_algo="SHA256withRSA",
        transmission_sig="sig_xyz",
        webhook_id="WH-123",
        webhook_event_payload={"id": "EVT-1"}
    )
    assert verified is True

