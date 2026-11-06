import time
import asyncio
import logging
from typing import Dict, Any, Optional, List
import httpx
from backend.app.config import settings

logger = logging.getLogger("paypal_client")


class PayPalError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class PayPalClient:
    """
    Robust PayPal REST API client strictly targeting the SANDBOX environment.
    Includes token caching, exponential backoff retries on 429/5xx, and full coverage of
    Invoicing v2, Payouts, Transaction Search, and Webhook verification.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.base_url = (base_url or settings.PAYPAL_BASE_URL).rstrip("/")
        self.client_id = client_id or settings.PAYPAL_CLIENT_ID
        self.client_secret = client_secret or settings.PAYPAL_CLIENT_SECRET

        # Strict Sandbox Enforcement
        if "sandbox.paypal.com" not in self.base_url:
            raise PayPalError(
                f"SAFETY VIOLATION: Refusing to initialize PayPal client. "
                f"Only Sandbox URL ('https://api-m.sandbox.paypal.com') is permitted. Got: {self.base_url}"
            )

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._lock = asyncio.Lock()

    async def _get_access_token(self, force_refresh: bool = False) -> str:
        """Fetches or reuses cached OAuth2 client-credentials access token."""
        async with self._lock:
            now = time.time()
            if self._access_token and (now < self._token_expires_at - 60) and not force_refresh:
                return self._access_token

            auth_url = f"{self.base_url}/v1/oauth2/token"
            data = {"grant_type": "client_credentials"}

            async with httpx.AsyncClient(timeout=15.0) as client:
                try:
                    response = await client.post(
                        auth_url,
                        data=data,
                        auth=(self.client_id, self.client_secret),
                        headers={"Accept": "application/json", "Accept-Language": "en_US"}
                    )
                except httpx.RequestError as exc:
                    raise PayPalError(f"Network error connecting to PayPal token endpoint: {exc}")

                if response.status_code != 200:
                    raise PayPalError(
                        f"OAuth2 authentication failed with status {response.status_code}: {response.text}",
                        status_code=response.status_code,
                        details=response.text
                    )

                token_data = response.json()
                self._access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)
                self._token_expires_at = now + expires_in
                return self._access_token

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Executes HTTP requests with token authentication and exponential backoff retry
        for transient 429 Rate Limit and 5xx Server Errors.
        """
        token = await self._get_access_token()
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        backoff = 0.5

        for attempt in range(1, max_retries + 1):
            async with httpx.AsyncClient(timeout=25.0) as client:
                try:
                    response = await client.request(
                        method=method,
                        url=url,
                        json=json_data,
                        params=params,
                        headers=req_headers
                    )
                except httpx.RequestError as exc:
                    if attempt == max_retries:
                        raise PayPalError(f"HTTP request failed after {max_retries} attempts: {exc}")
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

                # Handle rate limiting or server errors with backoff
                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt == max_retries:
                        raise PayPalError(
                            f"PayPal API error {response.status_code} after {max_retries} retries: {response.text}",
                            status_code=response.status_code,
                            details=response.text
                        )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

                # 401: Token might have been revoked; force refresh once
                if response.status_code == 401 and attempt == 1:
                    token = await self._get_access_token(force_refresh=True)
                    req_headers["Authorization"] = f"Bearer {token}"
                    continue

                if response.status_code not in (200, 201, 202, 204):
                    raise PayPalError(
                        f"PayPal API error {response.status_code} on {method} {endpoint}: {response.text}",
                        status_code=response.status_code,
                        details=response.text
                    )

                if response.status_code == 204 or not response.text.strip():
                    return {}

                return response.json()

    # --- Invoicing v2 Endpoints ---

    async def create_invoice(self, invoice_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Creates an invoice in DRAFT status."""
        return await self._request("POST", "/v2/invoicing/invoices", json_data=invoice_payload)

    async def send_invoice(self, invoice_id: str, note: Optional[str] = None) -> Dict[str, Any]:
        """Sends an invoice to the recipient."""
        payload = {}
        if note:
            payload["note"] = note
        return await self._request("POST", f"/v2/invoicing/invoices/{invoice_id}/send", json_data=payload)

    async def send_invoice_reminder(
        self,
        invoice_id: str,
        subject: str = "Payment Reminder: Upcoming Invoice Due",
        note: str = "Please find the invoice payment link attached for prompt settlement."
    ) -> Dict[str, Any]:
        """Sends an official PayPal invoice payment reminder email with action pay link."""
        payload = {
            "subject": subject,
            "note": note,
            "send_to_recipient": True,
            "send_to_invoicer": False
        }
        return await self._request("POST", f"/v2/invoicing/invoices/{invoice_id}/remind", json_data=payload)

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Retrieves invoice details, status, and payment link."""
        return await self._request("GET", f"/v2/invoicing/invoices/{invoice_id}")

    async def update_invoice(self, invoice_id: str, updated_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Updates full invoice details (e.g. to apply early-pay discount)."""
        return await self._request("PUT", f"/v2/invoicing/invoices/{invoice_id}", json_data=updated_payload)

    async def apply_invoice_discount(
        self,
        invoice_id: str,
        discount_percent: float,
        note: str = "Early payment discount applied."
    ) -> Dict[str, Any]:
        """Fetches existing invoice, applies discount percent, and updates it in sandbox."""
        current_inv = await self.get_invoice(invoice_id)
        # Apply discount to items or overall discount in detail
        detail = current_inv.get("detail", {})
        detail["discount"] = {
            "percent": f"{discount_percent:.2f}",
            "note": note
        }
        current_inv["detail"] = detail
        return await self.update_invoice(invoice_id, current_inv)

    # --- Payouts Endpoints ---

    async def create_payout(
        self,
        recipient_email: str,
        amount: float,
        currency: str,
        sender_batch_id: str,
        note: str = "Payment for contractor services",
        email_subject: str = "You have received a contractor payout"
    ) -> Dict[str, Any]:
        """
        Executes a batch payout to contractor.
        Uses sender_batch_id as idempotency key to prevent double execution.
        """
        payload = {
            "sender_batch_header": {
                "sender_batch_id": sender_batch_id,
                "email_subject": email_subject,
                "email_message": note
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "amount": {
                        "value": f"{amount:.2f}",
                        "currency": currency.upper()
                    },
                    "note": note,
                    "sender_item_id": f"item_{sender_batch_id}",
                    "receiver": recipient_email
                }
            ]
        }
        return await self._request("POST", "/v1/payments/payouts", json_data=payload)

    async def get_payout_batch(self, payout_batch_id: str) -> Dict[str, Any]:
        """Retrieves status of a payout batch."""
        return await self._request("GET", f"/v1/payments/payouts/{payout_batch_id}")

    # --- Transaction Search / Reporting ---

    async def list_transactions(
        self,
        start_date: str,
        end_date: str,
        page_size: int = 50,
        page: int = 1
    ) -> Dict[str, Any]:
        """Lists transactions between start_date and end_date (ISO 8601 YYYY-MM-DDTHH:MM:SSZ)."""
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "page_size": page_size,
            "page": page,
            "fields": "all"
        }
        return await self._request("GET", "/v1/reporting/transactions", params=params)

    # --- Webhooks Management & Verification ---

    async def verify_webhook_signature(
        self,
        transmission_id: str,
        transmission_time: str,
        cert_url: str,
        auth_algo: str,
        transmission_sig: str,
        webhook_id: str,
        webhook_event_payload: Dict[str, Any]
    ) -> bool:
        """
        Verifies the cryptographic signature of an incoming PayPal webhook via PayPal API.
        Returns True if verification_status == 'SUCCESS', False otherwise.
        """
        payload = {
            "transmission_id": transmission_id,
            "transmission_time": transmission_time,
            "cert_url": cert_url,
            "auth_algo": auth_algo,
            "transmission_sig": transmission_sig,
            "webhook_id": webhook_id,
            "webhook_event": webhook_event_payload
        }
        try:
            result = await self._request("POST", "/v1/notifications/verify-webhook-signature", json_data=payload)
            status = result.get("verification_status", "").upper()
            return status == "SUCCESS"
        except Exception as e:
            logger.warning(f"Webhook signature verification failed with error: {e}")
            return False

    async def register_webhook(self, webhook_url: str, event_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Registers a new webhook in the PayPal Sandbox."""
        if not event_types:
            event_types = [
                "INVOICING.INVOICE.PAID",
                "INVOICING.INVOICE.REFUNDED",
                "INVOICING.INVOICE.CANCELLED",
                "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
                "PAYMENT.PAYOUTS-ITEM.FAILED"
            ]

        payload = {
            "url": webhook_url,
            "event_types": [{"name": event_name} for event_name in event_types]
        }
        return await self._request("POST", "/v1/notifications/webhooks", json_data=payload)

    async def list_webhooks(self) -> Dict[str, Any]:
        """Lists registered webhooks."""
        return await self._request("GET", "/v1/notifications/webhooks")


# Singleton client instance
paypal_client = PayPalClient()

