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
)

router = APIRouter(tags=["Region & Localization"])


# -------------------------------------------------------------
# Region Detection & Catalogs
# -------------------------------------------------------------

@router.get("/region/detect", response_model=RegionDetectionResponse)
@router.get("/api/region/detect", response_model=RegionDetectionResponse)
async def detect_region(
    request: Request,
    client_hint: Optional[str] = None
):
    """
    Detect visitor country & suggest currency using trusted proxy headers,
    in-memory cached IP geolocation (1.5s timeout fallback), or Accept-Language.
    Never requires or prompts for GPS coordinates.
    """
    headers = {k.lower(): v for k, v in request.headers.items()}
    client_host = request.client.host if request.client else None

    result = await detect_region_info(
        headers=headers,
        client_host=client_host,
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

