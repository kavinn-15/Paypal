import asyncio
import sys
from backend.app.config import settings
from backend.app.paypal.client import paypal_client, PayPalError


async def main():
    public_url = settings.PUBLIC_BASE_URL.rstrip("/")
    webhook_url = f"{public_url}/webhooks/paypal"
    print(f"Registering PayPal Sandbox Webhook for: {webhook_url}")

    try:
        res = await paypal_client.register_webhook(webhook_url)
        webhook_id = res.get("id")
        print(f"SUCCESS: Webhook registered with ID: {webhook_id}")
        print(f"Add this to your .env file: PAYPAL_WEBHOOK_ID={webhook_id}")
    except PayPalError as e:
        print(f"Registration note: {e}")
        # List existing webhooks to find matching URL
        try:
            existing = await paypal_client.list_webhooks()
            hooks = existing.get("webhooks", [])
            print(f"Found {len(hooks)} existing webhook(s):")
            for h in hooks:
                print(f"- ID: {h.get('id')} -> {h.get('url')}")
        except Exception as ex:
            print(f"Failed to list webhooks: {ex}")


if __name__ == "__main__":
    asyncio.run(main())

