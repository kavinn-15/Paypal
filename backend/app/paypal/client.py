import time
import uuid
import asyncio
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, List
import httpx
from backend.app.config import settings
from backend.app.services.region_service import quantize_currency, get_currency_decimals

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
        request_id: Optional[str] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Executes HTTP requests with token authentication and exponential backoff retry
        for transient 429 Rate Limit and 5xx Server Errors.
        Idempotency header PayPal-Request-Id is attached for safe retry on mutations.
        """
        token = await self._get_access_token()
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if request_id:
            req_headers["PayPal-Request-Id"] = request_id
        if headers:
            req_headers.update(headers)

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        backoff = 0.5
        method_upper = method.upper()
        is_safe_read = method_upper in ("GET", "HEAD", "OPTIONS")
        has_idempotency = "PayPal-Request-Id" in req_headers

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
                    # Non-idempotent writes without an idempotency key cannot safely be retried on network timeout
                    if not is_safe_read and not has_idempotency:
                        raise PayPalError(f"HTTP non-idempotent write timed out or failed without idempotency key: {exc}")
                    if attempt == max_retries:
                        raise PayPalError(f"HTTP request failed after {max_retries} attempts: {exc}")
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

                # Handle rate limiting or server errors with backoff
                if response.status_code in (429, 500, 502, 503, 504):
                    if not is_safe_read and not has_idempotency and response.status_code != 429:
                        raise PayPalError(
                            f"PayPal API error {response.status_code} on non-idempotent write: {response.text}",
                            status_code=response.status_code,
                            details=response.text
                        )
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

    async def create_invoice(self, invoice_payload: Dict[str, Any], request_id: Optional[str] = None) -> Dict[str, Any]:
        """Creates an invoice in DRAFT status with safe idempotency protection."""
        req_id = request_id or str(uuid.uuid4())
        return await self._request("POST", "/v2/invoicing/invoices", json_data=invoice_payload, request_id=req_id)

    async def send_invoice(self, invoice_id: str, note: Optional[str] = None) -> Dict[str, Any]:
        """Sends an invoice to the recipient with idempotency header."""
        payload = {}
        if note:
            payload["note"] = note
        return await self._request("POST", f"/v2/invoicing/invoices/{invoice_id}/send", json_data=payload, request_id=f"send_{invoice_id}")

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
        req_id = f"remind_{invoice_id}_{int(time.time() // 300)}"
        return await self._request("POST", f"/v2/invoicing/invoices/{invoice_id}/remind", json_data=payload, request_id=req_id)

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Retrieves invoice details, status, and payment link."""
        return await self._request("GET", f"/v2/invoicing/invoices/{invoice_id}")

    async def update_invoice(self, invoice_id: str, updated_payload: Dict[str, Any], request_id: Optional[str] = None) -> Dict[str, Any]:
        """Updates full invoice details (e.g. to apply early-pay discount)."""
        return await self._request("PUT", f"/v2/invoicing/invoices/{invoice_id}", json_data=updated_payload, request_id=request_id)

    async def apply_invoice_discount(
        self,
        invoice_id: str,
        discount_percent: float,
        note: str = "Early payment discount applied."
    ) -> Dict[str, Any]:
        """
        Fetches existing invoice, applies discount percent, filters out read-only fields
        (id, status, metadata, links, amount, due_amount, payments, refunds), and updates it in sandbox.
        """
        current_inv = await self.get_invoice(invoice_id)
        # PayPal Invoicing v2 PUT allows only writable top-level fields
        writable_keys = ("detail", "invoicer", "primary_recipients", "additional_recipients", "items", "configuration")
        clean_inv = {k: current_inv[k] for k in writable_keys if k in current_inv}

        detail = clean_inv.get("detail", {})
        detail["discount"] = {
            "percent": f"{discount_percent:.2f}",
            "note": note
        }
        clean_inv["detail"] = detail

        # Quantize item unit_amounts to valid currency precision if present
        currency = detail.get("currency_code", "USD")
        if "items" in clean_inv and isinstance(clean_inv["items"], list):
            for item in clean_inv["items"]:
                unit_amt = item.get("unit_amount", {})
                if isinstance(unit_amt, dict) and "value" in unit_amt:
                    val = Decimal(str(unit_amt["value"]))
                    item_currency = unit_amt.get("currency_code", currency)
                    q_val = quantize_currency(val, item_currency)
                    decimals = get_currency_decimals(item_currency)
                    unit_amt["value"] = f"{int(q_val)}" if decimals == 0 else f"{q_val:.{decimals}f}"

        req_id = f"disc_{invoice_id}_{int(discount_percent * 100)}"
        return await self.update_invoice(invoice_id, clean_inv, request_id=req_id)

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
        currency_code = currency.upper().strip()
        dec_amount = quantize_currency(Decimal(str(amount)), currency_code)
        decimals = get_currency_decimals(currency_code)
        formatted_val = f"{int(dec_amount)}" if decimals == 0 else f"{dec_amount:.{decimals}f}"

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
                        "value": formatted_val,
                        "currency": currency_code
                    },
                    "note": note,
                    "sender_item_id": f"item_{sender_batch_id}",
                    "receiver": recipient_email
                }
            ]
        }
        return await self._request("POST", "/v1/payments/payouts", json_data=payload, request_id=sender_batch_id)

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
        Fails safely if webhook_id is unconfigured or dummy.
        """
        if not webhook_id or not str(webhook_id).strip() or str(webhook_id).strip().lower() in ("sandbox_wh_id", "dummy_webhook_id", "none"):
            logger.warning("Refusing to verify webhook signature: invalid or dummy webhook_id configured.")
            return False

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

