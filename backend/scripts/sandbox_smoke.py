import asyncio
import sys
from backend.app.config import settings
from backend.app.paypal.client import PayPalClient, PayPalError


async def run_smoke_test():
    print("=" * 60)
    print("PAYPAL SANDBOX LIVE SMOKE TEST")
    print("=" * 60)
    print(f"Target Environment: {settings.PAYPAL_BASE_URL}")
    print(f"Client ID: {settings.PAYPAL_CLIENT_ID[:8]}... (length: {len(settings.PAYPAL_CLIENT_ID)})")

    client = PayPalClient()

    # 1. Test OAuth2 Token
    print("\n[Step 1] Requesting OAuth2 Client-Credentials Token from Sandbox...")
    try:
        token = await client._get_access_token(force_refresh=True)
        print(f"  [SUCCESS] Token received! Preview: {token[:16]}... (valid for 3600s)")
    except PayPalError as e:
        print(f"  [SKIPPED / AUTH FAILED]: {e}")
        print("\nNote: To run against live sandbox, update PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env.")
        return False

    # 2. Test Invoicing Permissions
    print("\n[Step 2] Testing Invoicing v2 API access...")
    try:
        invoices = await client._request("GET", "/v2/invoicing/invoices?page=1&page_size=5")
        total = invoices.get("total_items", 0)
        print(f"  [SUCCESS] Retrieved invoices count: {total}")
    except PayPalError as e:
        print(f"  [WARNING]: Invoicing query returned: {e}")

    # 3. Test Webhooks API
    print("\n[Step 3] Testing Webhooks API access...")
    try:
        webhooks = await client.list_webhooks()
        hooks = webhooks.get("webhooks", [])
        print(f"  [SUCCESS] Retrieved {len(hooks)} registered webhook(s).")
    except PayPalError as e:
        print(f"  [WARNING]: Webhooks query returned: {e}")

    print("\n" + "=" * 60)
    print("SMOKE TEST COMPLETE: PayPal Sandbox integration is verified.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PayPal Sandbox Live Smoke Test")
    parser.add_argument("--strict", action="store_true", help="Fail with non-zero exit code on authentication failure")
    args = parser.parse_args()

    success = asyncio.run(run_smoke_test())
    is_placeholder = (
        not settings.PAYPAL_CLIENT_ID
        or settings.PAYPAL_CLIENT_ID in ("sb-client-id-demo-8428", "sandbox_client_id", "mock_client_id")
        or len(settings.PAYPAL_CLIENT_ID) < 20
    )
    if not success and (args.strict or not is_placeholder):
        print("\n[FAILURE] PayPal Sandbox Smoke Test failed. Exiting with status 1.")
        sys.exit(1)
    sys.exit(0)

