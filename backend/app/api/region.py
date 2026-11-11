import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Owner
from backend.app.auth.deps import get_current_user
from backend.app.guardrail.audit import append_audit_log
from backend.app.schemas import (
    RegionDetectionResponse,
    CountryItem,
    CurrencyItem,
    RegionalPreferencesResponse,
    RegionalPreferencesUpdate,
)
from backend.app.services.region_service import (
    detect_region_info,
    list_all_countries,
    list_all_currencies,
    COUNTRIES_DB,
    CURRENCIES_DB,
    BENCHMARK_EXCHANGE_RATES,
    get_exchange_rate,
)

router = APIRouter(tags=["Region & Localization"])


# -------------------------------------------------------------
# Region Detection & Catalogs
# -------------------------------------------------------------

@router.get("/region/detect", response_model=RegionDetectionResponse)
@router.get("/api/region/detect", response_model=RegionDetectionResponse)
async def detect_region(
    request: Request,
    timezone: Optional[str] = None,
    client_hint: Optional[str] = None
):
    """
    Detect visitor country & suggest currency using trusted proxy headers,
    in-memory cached IP geolocation (1.5s timeout fallback), Accept-Language,
    or browser timezone. Never requires or prompts for GPS coordinates.
    """
    headers = {k.lower(): v for k, v in request.headers.items()}
    client_host = request.client.host if request.client else None
    effective_tz = timezone or headers.get("x-timezone")

    result = await detect_region_info(
        headers=headers,
        client_host=client_host,
        timezone=effective_tz,
        client_hint_country=client_hint
    )
    return result


@router.get("/region/countries", response_model=List[CountryItem])
@router.get("/api/region/countries", response_model=List[CountryItem])
def get_countries():
    """
    List all supported countries with metadata, flags, dial codes, and default currencies.
    Popular countries are ranked at top.
    """
    return list_all_countries()


@router.get("/region/currencies", response_model=List[CurrencyItem])
@router.get("/api/region/currencies", response_model=List[CurrencyItem])
def get_currencies():
    """
    List all supported currencies with ISO 4217 code, name, symbol, and decimals.
    """
    return list_all_currencies()


@router.get("/region/rates")
@router.get("/api/region/rates")
def get_exchange_rates(from_currency: Optional[str] = "USD", to_currency: Optional[str] = None):
    """
    Retrieve authoritative currency conversion rates relative to USD baseline.
    Optionally returns direct cross-currency rate between two currencies.
    Never silently returns 1.0 for unknown currency pairs.
    """
    from_code = (from_currency or "USD").strip().upper()
    if to_currency:
        to_code = to_currency.strip().upper()
        rate = get_exchange_rate(from_code, to_code)
        if rate is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Exchange rate between {from_code} and {to_code} is unavailable."
            )
        return {
            "from_currency": from_code,
            "to_currency": to_code,
            "rate": rate,
            "source": "central_bank_benchmark",
            "is_stale": False,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }
    return {
        "base": "USD",
        "base_currency": "USD",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "source": "central_bank_benchmark",
        "is_stale": False,
        "rates": BENCHMARK_EXCHANGE_RATES,
        "paypal_supported_currencies": [
            "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "SGD", "CHF", "NZD",
            "SEK", "NOK", "DKK", "PLN", "BRL", "MXN", "ILS", "PHP", "THB", "TWD", "CZK", "HUF"
        ]
    }


# -------------------------------------------------------------
# User Regional Preferences (Protected)
# -------------------------------------------------------------

def _build_preferences_response(user: Owner) -> RegionalPreferencesResponse:
    country_code = (user.country or "US").upper()
    country_meta = COUNTRIES_DB.get(country_code, COUNTRIES_DB["US"])
    pref_curr = (user.preferred_currency or user.currency or "USD").upper()
    curr_meta = CURRENCIES_DB.get(pref_curr, {"code": pref_curr, "symbol": pref_curr})

    return RegionalPreferencesResponse(
        country=country_code,
        country_name=country_meta.get("name", country_code),
        flag=country_meta.get("flag", "🌐"),
        currency=user.currency,
        preferred_currency=pref_curr,
        currency_symbol=curr_meta.get("symbol", "$"),
        locale=user.locale or "en-US",
        region_detection_enabled=bool(user.region_detection_enabled),
        region_preference_source=user.region_preference_source or "detected",
        updated_at=user.region_preferences_updated_at,
    )


@router.get("/profile/regional-preferences", response_model=RegionalPreferencesResponse)
@router.get("/api/profile/regional-preferences", response_model=RegionalPreferencesResponse)
def get_regional_preferences(current_user: Owner = Depends(get_current_user)):
    """
    Retrieve authenticated user's current regional, country, and currency preferences.
    """
    return _build_preferences_response(current_user)


@router.put("/profile/regional-preferences", response_model=RegionalPreferencesResponse)
@router.put("/api/profile/regional-preferences", response_model=RegionalPreferencesResponse)
def update_regional_preferences(
    req: RegionalPreferencesUpdate,
    current_user: Owner = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update regional preferences for the authenticated user.
    Maintains financial safety: Base ledger currency is preserved unless explicitly modified.
    """
    changes = {}

    if req.country is not None:
        country_code = req.country.strip().upper()
        if country_code not in COUNTRIES_DB:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported country code: {req.country}"
            )
        current_user.country = country_code
        changes["country"] = country_code

    if req.preferred_currency is not None:
        curr = req.preferred_currency.strip().upper()
        if curr not in CURRENCIES_DB:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported currency code: {req.preferred_currency}"
            )
        current_user.preferred_currency = curr
        changes["preferred_currency"] = curr

    if req.currency is not None:
        # Base ledger currency update
        base_curr = req.currency.strip().upper()
        if base_curr not in CURRENCIES_DB:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported base currency code: {req.currency}"
            )
        current_user.currency = base_curr
        changes["base_currency"] = base_curr

    if req.locale is not None:
        current_user.locale = req.locale.strip()
        changes["locale"] = current_user.locale

    if req.region_detection_enabled is not None:
        current_user.region_detection_enabled = req.region_detection_enabled
        changes["region_detection_enabled"] = req.region_detection_enabled

    current_user.region_preference_source = "manual"
    current_user.region_preferences_updated_at = datetime.datetime.utcnow()
    changes["preference_source"] = "manual"

    db.commit()
    db.refresh(current_user)

    append_audit_log(
        db,
        actor="owner",
        event="REGIONAL_PREFERENCES_UPDATED",
        payload={
            "user_id": current_user.id,
            "changes": changes,
            "updated_at": current_user.region_preferences_updated_at.isoformat()
        }
    )

    return _build_preferences_response(current_user)

