"""
Comprehensive Region, Country and Currency Service for Cashflow Lifeline.
Provides ISO 3166-1 country metadata, ISO 4217 currency mappings,
strict trusted-proxy IP detection, resilient multi-provider IP geolocation,
browser locale/timezone fallback, and privacy-preserving in-memory caching.
"""

import ipaddress
import logging
import time
from typing import Dict, Any, List, Optional
import httpx

from backend.app.config import settings

logger = logging.getLogger("region_service")

# In-memory TTL cache for IP geolocation lookups: {ip_str: (timestamp, result_dict)}
_IP_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 86400  # 24 hours

# Zero-decimal and three-decimal currencies for accurate financial formatting
ZERO_DECIMAL_CURRENCIES = {
    "BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA",
    "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"
}

THREE_DECIMAL_CURRENCIES = {
    "BHD", "IQD", "JOD", "KWD", "OMR", "TND"
}

# Major Currencies Metadata: Code -> Details
CURRENCIES_DB: Dict[str, Dict[str, Any]] = {
    "USD": {"code": "USD", "name": "US Dollar", "symbol": "$", "decimals": 2},
    "EUR": {"code": "EUR", "name": "Euro", "symbol": "€", "decimals": 2},
    "GBP": {"code": "GBP", "name": "British Pound", "symbol": "£", "decimals": 2},
    "INR": {"code": "INR", "name": "Indian Rupee", "symbol": "₹", "decimals": 2},
    "CAD": {"code": "CAD", "name": "Canadian Dollar", "symbol": "CA$", "decimals": 2},
    "AUD": {"code": "AUD", "name": "Australian Dollar", "symbol": "A$", "decimals": 2},
    "JPY": {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "decimals": 0},
    "SGD": {"code": "SGD", "name": "Singapore Dollar", "symbol": "S$", "decimals": 2},
    "AED": {"code": "AED", "name": "UAE Dirham", "symbol": "AED", "decimals": 2},
    "CHF": {"code": "CHF", "name": "Swiss Franc", "symbol": "CHF", "decimals": 2},
    "CNY": {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥", "decimals": 2},
    "HKD": {"code": "HKD", "name": "Hong Kong Dollar", "symbol": "HK$", "decimals": 2},
    "NZD": {"code": "NZD", "name": "New Zealand Dollar", "symbol": "NZ$", "decimals": 2},
    "SEK": {"code": "SEK", "name": "Swedish Krona", "symbol": "kr", "decimals": 2},
    "NOK": {"code": "NOK", "name": "Norwegian Krone", "symbol": "kr", "decimals": 2},
    "DKK": {"code": "DKK", "name": "Danish Krone", "symbol": "kr.", "decimals": 2},
    "PLN": {"code": "PLN", "name": "Polish Zloty", "symbol": "zł", "decimals": 2},
    "BRL": {"code": "BRL", "name": "Brazilian Real", "symbol": "R$", "decimals": 2},
    "MXN": {"code": "MXN", "name": "Mexican Peso", "symbol": "MX$", "decimals": 2},
    "ZAR": {"code": "ZAR", "name": "South African Rand", "symbol": "R", "decimals": 2},
    "SAR": {"code": "SAR", "name": "Saudi Riyal", "symbol": "SAR", "decimals": 2},
    "TRY": {"code": "TRY", "name": "Turkish Lira", "symbol": "₺", "decimals": 2},
    "KRW": {"code": "KRW", "name": "South Korean Won", "symbol": "₩", "decimals": 0},
    "IDR": {"code": "IDR", "name": "Indonesian Rupiah", "symbol": "Rp", "decimals": 2},
    "MYR": {"code": "MYR", "name": "Malaysian Ringgit", "symbol": "RM", "decimals": 2},
    "PHP": {"code": "PHP", "name": "Philippine Peso", "symbol": "₱", "decimals": 2},
    "THB": {"code": "THB", "name": "Thai Baht", "symbol": "฿", "decimals": 2},
    "VND": {"code": "VND", "name": "Vietnamese Dong", "symbol": "₫", "decimals": 0},
    "ILS": {"code": "ILS", "name": "Israeli New Shekel", "symbol": "₪", "decimals": 2},
    "CLP": {"code": "CLP", "name": "Chilean Peso", "symbol": "CLP$", "decimals": 0},
    "COP": {"code": "COP", "name": "Colombian Peso", "symbol": "COL$", "decimals": 2},
    "ARS": {"code": "ARS", "name": "Argentine Peso", "symbol": "AR$", "decimals": 2},
    "EGP": {"code": "EGP", "name": "Egyptian Pound", "symbol": "E£", "decimals": 2},
    "NGN": {"code": "NGN", "name": "Nigerian Naira", "symbol": "₦", "decimals": 2},
    "KES": {"code": "KES", "name": "Kenyan Shilling", "symbol": "KSh", "decimals": 2},
    "QAR": {"code": "QAR", "name": "Qatari Riyal", "symbol": "QR", "decimals": 2},
    "KWD": {"code": "KWD", "name": "Kuwaiti Dinar", "symbol": "KD", "decimals": 3},
    "BHD": {"code": "BHD", "name": "Bahraini Dinar", "symbol": "BD", "decimals": 3},
    "OMR": {"code": "OMR", "name": "Omani Rial", "symbol": "OMR", "decimals": 3},
    "HUF": {"code": "HUF", "name": "Hungarian Forint", "symbol": "Ft", "decimals": 2},
    "CZK": {"code": "CZK", "name": "Czech Koruna", "symbol": "Kč", "decimals": 2},
    "RON": {"code": "RON", "name": "Romanian Leu", "symbol": "lei", "decimals": 2},
    "BGN": {"code": "BGN", "name": "Bulgarian Lev", "symbol": "лв", "decimals": 2},
    "ISK": {"code": "ISK", "name": "Icelandic Krona", "symbol": "kr", "decimals": 0},
    "TWD": {"code": "TWD", "name": "New Taiwan Dollar", "symbol": "NT$", "decimals": 2},
    "PKR": {"code": "PKR", "name": "Pakistani Rupee", "symbol": "Rs", "decimals": 2},
    "BDT": {"code": "BDT", "name": "Bangladeshi Taka", "symbol": "৳", "decimals": 2},
    "LKR": {"code": "LKR", "name": "Sri Lankan Rupee", "symbol": "Rs", "decimals": 2},
    "MAD": {"code": "MAD", "name": "Moroccan Dirham", "symbol": "MAD", "decimals": 2},
}

# Comprehensive Country Data (ISO 3166-1 alpha-2)
COUNTRIES_DB: Dict[str, Dict[str, Any]] = {
    "US": {"code": "US", "name": "United States", "flag": "🇺🇸", "currency": "USD", "dial_code": "+1", "locale": "en-US", "popular": True},
    "IN": {"code": "IN", "name": "India", "flag": "🇮🇳", "currency": "INR", "dial_code": "+91", "locale": "en-IN", "popular": True},
    "GB": {"code": "GB", "name": "United Kingdom", "flag": "🇬🇧", "currency": "GBP", "dial_code": "+44", "locale": "en-GB", "popular": True},
    "CA": {"code": "CA", "name": "Canada", "flag": "🇨🇦", "currency": "CAD", "dial_code": "+1", "locale": "en-CA", "popular": True},
    "AU": {"code": "AU", "name": "Australia", "flag": "🇦🇺", "currency": "AUD", "dial_code": "+61", "locale": "en-AU", "popular": True},
    "DE": {"code": "DE", "name": "Germany", "flag": "🇩🇪", "currency": "EUR", "dial_code": "+49", "locale": "de-DE", "popular": True},
    "FR": {"code": "FR", "name": "France", "flag": "🇫🇷", "currency": "EUR", "dial_code": "+33", "locale": "fr-FR", "popular": True},
    "JP": {"code": "JP", "name": "Japan", "flag": "🇯🇵", "currency": "JPY", "dial_code": "+81", "locale": "ja-JP", "popular": True},
    "SG": {"code": "SG", "name": "Singapore", "flag": "🇸🇬", "currency": "SGD", "dial_code": "+65", "locale": "en-SG", "popular": True},
    "AE": {"code": "AE", "name": "United Arab Emirates", "flag": "🇦🇪", "currency": "AED", "dial_code": "+971", "locale": "ar-AE", "popular": True},
    "NL": {"code": "NL", "name": "Netherlands", "flag": "🇳🇱", "currency": "EUR", "dial_code": "+31", "locale": "nl-NL", "popular": True},
    "CH": {"code": "CH", "name": "Switzerland", "flag": "🇨🇭", "currency": "CHF", "dial_code": "+41", "locale": "de-CH", "popular": True},
    "SE": {"code": "SE", "name": "Sweden", "flag": "🇸🇪", "currency": "SEK", "dial_code": "+46", "locale": "sv-SE", "popular": True},
    "IE": {"code": "IE", "name": "Ireland", "flag": "🇮🇪", "currency": "EUR", "dial_code": "+353", "locale": "en-IE", "popular": True},
    "ES": {"code": "ES", "name": "Spain", "flag": "🇪🇸", "currency": "EUR", "dial_code": "+34", "locale": "es-ES", "popular": True},
    "IT": {"code": "IT", "name": "Italy", "flag": "🇮🇹", "currency": "EUR", "dial_code": "+39", "locale": "it-IT", "popular": True},
    "BR": {"code": "BR", "name": "Brazil", "flag": "🇧🇷", "currency": "BRL", "dial_code": "+55", "locale": "pt-BR", "popular": True},
    "MX": {"code": "MX", "name": "Mexico", "flag": "🇲🇽", "currency": "MXN", "dial_code": "+52", "locale": "es-MX", "popular": True},
    "ZA": {"code": "ZA", "name": "South Africa", "flag": "🇿🇦", "currency": "ZAR", "dial_code": "+27", "locale": "en-ZA", "popular": True},
    "NZ": {"code": "NZ", "name": "New Zealand", "flag": "🇳🇿", "currency": "NZD", "dial_code": "+64", "locale": "en-NZ", "popular": True},
    "AF": {"code": "AF", "name": "Afghanistan", "flag": "🇦🇫", "currency": "AFN", "dial_code": "+93", "locale": "fa-AF", "popular": False},
    "AL": {"code": "AL", "name": "Albania", "flag": "🇦🇱", "currency": "ALL", "dial_code": "+355", "locale": "sq-AL", "popular": False},
    "DZ": {"code": "DZ", "name": "Algeria", "flag": "🇩🇿", "currency": "DZD", "dial_code": "+213", "locale": "ar-DZ", "popular": False},
    "AD": {"code": "AD", "name": "Andorra", "flag": "🇦🇩", "currency": "EUR", "dial_code": "+376", "locale": "ca-AD", "popular": False},
    "AO": {"code": "AO", "name": "Angola", "flag": "🇦🇴", "currency": "AOA", "dial_code": "+244", "locale": "pt-AO", "popular": False},
    "AG": {"code": "AG", "name": "Antigua and Barbuda", "flag": "🇦🇬", "currency": "XCD", "dial_code": "+1-268", "locale": "en-AG", "popular": False},
    "AR": {"code": "AR", "name": "Argentina", "flag": "🇦🇷", "currency": "ARS", "dial_code": "+54", "locale": "es-AR", "popular": False},
    "AM": {"code": "AM", "name": "Armenia", "flag": "🇦🇲", "currency": "AMD", "dial_code": "+374", "locale": "hy-AM", "popular": False},
    "AT": {"code": "AT", "name": "Austria", "flag": "🇦🇹", "currency": "EUR", "dial_code": "+43", "locale": "de-AT", "popular": False},
    "AZ": {"code": "AZ", "name": "Azerbaijan", "flag": "🇦🇿", "currency": "AZN", "dial_code": "+994", "locale": "az-AZ", "popular": False},
    "BS": {"code": "BS", "name": "Bahamas", "flag": "🇧🇸", "currency": "BSD", "dial_code": "+1-242", "locale": "en-BS", "popular": False},
    "BH": {"code": "BH", "name": "Bahrain", "flag": "🇧🇭", "currency": "BHD", "dial_code": "+973", "locale": "ar-BH", "popular": False},
    "BD": {"code": "BD", "name": "Bangladesh", "flag": "🇧🇩", "currency": "BDT", "dial_code": "+880", "locale": "bn-BD", "popular": False},
    "BB": {"code": "BB", "name": "Barbados", "flag": "🇧🇧", "currency": "BBD", "dial_code": "+1-246", "locale": "en-BB", "popular": False},
    "BY": {"code": "BY", "name": "Belarus", "flag": "🇧🇾", "currency": "BYN", "dial_code": "+375", "locale": "be-BY", "popular": False},
    "BE": {"code": "BE", "name": "Belgium", "flag": "🇧🇪", "currency": "EUR", "dial_code": "+32", "locale": "nl-BE", "popular": False},
    "BZ": {"code": "BZ", "name": "Belize", "flag": "🇧🇿", "currency": "BZD", "dial_code": "+501", "locale": "en-BZ", "popular": False},
    "BJ": {"code": "BJ", "name": "Benin", "flag": "🇧🇯", "currency": "XOF", "dial_code": "+229", "locale": "fr-BJ", "popular": False},
    "BT": {"code": "BT", "name": "Bhutan", "flag": "🇧🇹", "currency": "BTN", "dial_code": "+975", "locale": "dz-BT", "popular": False},
    "BO": {"code": "BO", "name": "Bolivia", "flag": "🇧🇴", "currency": "BOB", "dial_code": "+591", "locale": "es-BO", "popular": False},
    "BA": {"code": "BA", "name": "Bosnia and Herzegovina", "flag": "🇧🇦", "currency": "BAM", "dial_code": "+387", "locale": "bs-BA", "popular": False},
    "BW": {"code": "BW", "name": "Botswana", "flag": "🇧🇼", "currency": "BWP", "dial_code": "+267", "locale": "en-BW", "popular": False},
    "BN": {"code": "BN", "name": "Brunei", "flag": "🇧🇳", "currency": "BND", "dial_code": "+673", "locale": "ms-BN", "popular": False},
    "BG": {"code": "BG", "name": "Bulgaria", "flag": "🇧🇬", "currency": "BGN", "dial_code": "+359", "locale": "bg-BG", "popular": False},
    "BF": {"code": "BF", "name": "Burkina Faso", "flag": "🇧🇫", "currency": "XOF", "dial_code": "+226", "locale": "fr-BF", "popular": False},
    "BI": {"code": "BI", "name": "Burundi", "flag": "🇧🇮", "currency": "BIF", "dial_code": "+257", "locale": "fr-BI", "popular": False},
    "KH": {"code": "KH", "name": "Cambodia", "flag": "🇰🇭", "currency": "KHR", "dial_code": "+855", "locale": "km-KH", "popular": False},
    "CM": {"code": "CM", "name": "Cameroon", "flag": "🇨🇲", "currency": "XAF", "dial_code": "+237", "locale": "fr-CM", "popular": False},
    "CV": {"code": "CV", "name": "Cape Verde", "flag": "🇨🇻", "currency": "CVE", "dial_code": "+238", "locale": "pt-CV", "popular": False},
    "CL": {"code": "CL", "name": "Chile", "flag": "🇨🇱", "currency": "CLP", "dial_code": "+56", "locale": "es-CL", "popular": False},
    "CN": {"code": "CN", "name": "China", "flag": "🇨🇳", "currency": "CNY", "dial_code": "+86", "locale": "zh-CN", "popular": False},
    "CO": {"code": "CO", "name": "Colombia", "flag": "🇨🇴", "currency": "COP", "dial_code": "+57", "locale": "es-CO", "popular": False},
    "CR": {"code": "CR", "name": "Costa Rica", "flag": "🇨🇷", "currency": "CRC", "dial_code": "+506", "locale": "es-CR", "popular": False},
    "HR": {"code": "HR", "name": "Croatia", "flag": "🇭🇷", "currency": "EUR", "dial_code": "+385", "locale": "hr-HR", "popular": False},
    "CY": {"code": "CY", "name": "Cyprus", "flag": "🇨🇾", "currency": "EUR", "dial_code": "+357", "locale": "el-CY", "popular": False},
    "CZ": {"code": "CZ", "name": "Czech Republic", "flag": "🇨🇿", "currency": "CZK", "dial_code": "+420", "locale": "cs-CZ", "popular": False},
    "DK": {"code": "DK", "name": "Denmark", "flag": "🇩🇰", "currency": "DKK", "dial_code": "+45", "locale": "da-DK", "popular": False},
    "DO": {"code": "DO", "name": "Dominican Republic", "flag": "🇩🇴", "currency": "DOP", "dial_code": "+1-809", "locale": "es-DO", "popular": False},
    "EC": {"code": "EC", "name": "Ecuador", "flag": "🇪🇨", "currency": "USD", "dial_code": "+593", "locale": "es-EC", "popular": False},
    "EG": {"code": "EG", "name": "Egypt", "flag": "🇪🇬", "currency": "EGP", "dial_code": "+20", "locale": "ar-EG", "popular": False},
    "EE": {"code": "EE", "name": "Estonia", "flag": "🇪🇪", "currency": "EUR", "dial_code": "+372", "locale": "et-EE", "popular": False},
    "ET": {"code": "ET", "name": "Ethiopia", "flag": "🇪🇹", "currency": "ETB", "dial_code": "+251", "locale": "am-ET", "popular": False},
    "FI": {"code": "FI", "name": "Finland", "flag": "🇫🇮", "currency": "EUR", "dial_code": "+358", "locale": "fi-FI", "popular": False},
    "GE": {"code": "GE", "name": "Georgia", "flag": "🇬🇪", "currency": "GEL", "dial_code": "+995", "locale": "ka-GE", "popular": False},
    "GH": {"code": "GH", "name": "Ghana", "flag": "🇬🇭", "currency": "GHS", "dial_code": "+233", "locale": "en-GH", "popular": False},
    "GR": {"code": "GR", "name": "Greece", "flag": "🇬🇷", "currency": "EUR", "dial_code": "+30", "locale": "el-GR", "popular": False},
    "GT": {"code": "GT", "name": "Guatemala", "flag": "🇬🇹", "currency": "GTQ", "dial_code": "+502", "locale": "es-GT", "popular": False},
    "HK": {"code": "HK", "name": "Hong Kong", "flag": "🇭🇰", "currency": "HKD", "dial_code": "+852", "locale": "zh-HK", "popular": False},
    "HU": {"code": "HU", "name": "Hungary", "flag": "🇭🇺", "currency": "HUF", "dial_code": "+36", "locale": "hu-HU", "popular": False},
    "IS": {"code": "IS", "name": "Iceland", "flag": "🇮🇸", "currency": "ISK", "dial_code": "+354", "locale": "is-IS", "popular": False},
    "ID": {"code": "ID", "name": "Indonesia", "flag": "🇮🇩", "currency": "IDR", "dial_code": "+62", "locale": "id-ID", "popular": False},
    "IQ": {"code": "IQ", "name": "Iraq", "flag": "🇮🇶", "currency": "IQD", "dial_code": "+964", "locale": "ar-IQ", "popular": False},
    "IL": {"code": "IL", "name": "Israel", "flag": "🇮🇱", "currency": "ILS", "dial_code": "+972", "locale": "he-IL", "popular": False},
    "JM": {"code": "JM", "name": "Jamaica", "flag": "🇯🇲", "currency": "JMD", "dial_code": "+1-876", "locale": "en-JM", "popular": False},
    "JO": {"code": "JO", "name": "Jordan", "flag": "🇯🇴", "currency": "JOD", "dial_code": "+962", "locale": "ar-JO", "popular": False},
    "KZ": {"code": "KZ", "name": "Kazakhstan", "flag": "🇰🇿", "currency": "KZT", "dial_code": "+7", "locale": "kk-KZ", "popular": False},
    "KE": {"code": "KE", "name": "Kenya", "flag": "🇰🇪", "currency": "KES", "dial_code": "+254", "locale": "sw-KE", "popular": False},
    "KR": {"code": "KR", "name": "South Korea", "flag": "🇰🇷", "currency": "KRW", "dial_code": "+82", "locale": "ko-KR", "popular": False},
    "KW": {"code": "KW", "name": "Kuwait", "flag": "🇰🇼", "currency": "KWD", "dial_code": "+965", "locale": "ar-KW", "popular": False},
    "LV": {"code": "LV", "name": "Latvia", "flag": "🇱🇻", "currency": "EUR", "dial_code": "+371", "locale": "lv-LV", "popular": False},
    "LB": {"code": "LB", "name": "Lebanon", "flag": "🇱🇧", "currency": "LBP", "dial_code": "+961", "locale": "ar-LB", "popular": False},
    "LT": {"code": "LT", "name": "Lithuania", "flag": "🇱🇹", "currency": "EUR", "dial_code": "+370", "locale": "lt-LT", "popular": False},
    "LU": {"code": "LU", "name": "Luxembourg", "flag": "🇱🇺", "currency": "EUR", "dial_code": "+352", "locale": "fr-LU", "popular": False},
    "MY": {"code": "MY", "name": "Malaysia", "flag": "🇲🇾", "currency": "MYR", "dial_code": "+60", "locale": "ms-MY", "popular": False},
    "MV": {"code": "MV", "name": "Maldives", "flag": "🇲🇻", "currency": "MVR", "dial_code": "+960", "locale": "dv-MV", "popular": False},
    "MT": {"code": "MT", "name": "Malta", "flag": "🇲🇹", "currency": "EUR", "dial_code": "+356", "locale": "mt-MT", "popular": False},
    "MU": {"code": "MU", "name": "Mauritius", "flag": "🇲🇺", "currency": "MUR", "dial_code": "+230", "locale": "en-MU", "popular": False},
    "MA": {"code": "MA", "name": "Morocco", "flag": "🇲🇦", "currency": "MAD", "dial_code": "+212", "locale": "ar-MA", "popular": False},
    "NP": {"code": "NP", "name": "Nepal", "flag": "🇳🇵", "currency": "NPR", "dial_code": "+977", "locale": "ne-NP", "popular": False},
    "NG": {"code": "NG", "name": "Nigeria", "flag": "🇳🇬", "currency": "NGN", "dial_code": "+234", "locale": "en-NG", "popular": False},
    "NO": {"code": "NO", "name": "Norway", "flag": "🇳🇴", "currency": "NOK", "dial_code": "+47", "locale": "nb-NO", "popular": False},
    "OM": {"code": "OM", "name": "Oman", "flag": "🇴🇲", "currency": "OMR", "dial_code": "+968", "locale": "ar-OM", "popular": False},
    "PK": {"code": "PK", "name": "Pakistan", "flag": "🇵🇰", "currency": "PKR", "dial_code": "+92", "locale": "ur-PK", "popular": False},
    "PA": {"code": "PA", "name": "Panama", "flag": "🇵🇦", "currency": "USD", "dial_code": "+507", "locale": "es-PA", "popular": False},
    "PY": {"code": "PY", "name": "Paraguay", "flag": "🇵🇾", "currency": "PYG", "dial_code": "+595", "locale": "es-PY", "popular": False},
    "PE": {"code": "PE", "name": "Peru", "flag": "🇵🇪", "currency": "PEN", "dial_code": "+51", "locale": "es-PE", "popular": False},
    "PH": {"code": "PH", "name": "Philippines", "flag": "🇵🇭", "currency": "PHP", "dial_code": "+63", "locale": "en-PH", "popular": False},
    "PL": {"code": "PL", "name": "Poland", "flag": "🇵🇱", "currency": "PLN", "dial_code": "+48", "locale": "pl-PL", "popular": False},
    "PT": {"code": "PT", "name": "Portugal", "flag": "🇵🇹", "currency": "EUR", "dial_code": "+351", "locale": "pt-PT", "popular": False},
    "QA": {"code": "QA", "name": "Qatar", "flag": "🇶🇦", "currency": "QAR", "dial_code": "+974", "locale": "ar-QA", "popular": False},
    "RO": {"code": "RO", "name": "Romania", "flag": "🇷🇴", "currency": "RON", "dial_code": "+40", "locale": "ro-RO", "popular": False},
    "SA": {"code": "SA", "name": "Saudi Arabia", "flag": "🇸🇦", "currency": "SAR", "dial_code": "+966", "locale": "ar-SA", "popular": False},
    "RS": {"code": "RS", "name": "Serbia", "flag": "🇷🇸", "currency": "RSD", "dial_code": "+381", "locale": "sr-RS", "popular": False},
    "SK": {"code": "SK", "name": "Slovakia", "flag": "🇸🇰", "currency": "EUR", "dial_code": "+421", "locale": "sk-SK", "popular": False},
    "SI": {"code": "SI", "name": "Slovenia", "flag": "🇸🇮", "currency": "EUR", "dial_code": "+386", "locale": "sl-SI", "popular": False},
    "LK": {"code": "LK", "name": "Sri Lanka", "flag": "🇱🇰", "currency": "LKR", "dial_code": "+94", "locale": "si-LK", "popular": False},
    "TW": {"code": "TW", "name": "Taiwan", "flag": "🇹🇼", "currency": "TWD", "dial_code": "+886", "locale": "zh-TW", "popular": False},
    "TH": {"code": "TH", "name": "Thailand", "flag": "🇹🇭", "currency": "THB", "dial_code": "+66", "locale": "th-TH", "popular": False},
    "TR": {"code": "TR", "name": "Turkey", "flag": "🇹🇷", "currency": "TRY", "dial_code": "+90", "locale": "tr-TR", "popular": False},
    "UA": {"code": "UA", "name": "Ukraine", "flag": "🇺🇦", "currency": "UAH", "dial_code": "+380", "locale": "uk-UA", "popular": False},
    "UY": {"code": "UY", "name": "Uruguay", "flag": "🇺🇾", "currency": "UYU", "dial_code": "+598", "locale": "es-UY", "popular": False},
    "VN": {"code": "VN", "name": "Vietnam", "flag": "🇻🇳", "currency": "VND", "dial_code": "+84", "locale": "vi-VN", "popular": False},
}

# Common timezone to country mapping
TIMEZONE_COUNTRY_MAP: Dict[str, str] = {
    "Asia/Kolkata": "IN",
    "Asia/Calcutta": "IN",
    "Europe/London": "GB",
    "America/New_York": "US",
    "America/Chicago": "US",
    "America/Denver": "US",
    "America/Los_Angeles": "US",
    "America/Phoenix": "US",
    "America/Anchorage": "US",
    "America/Honolulu": "US",
    "America/Toronto": "CA",
    "America/Vancouver": "CA",
    "America/Montreal": "CA",
    "Australia/Sydney": "AU",
    "Australia/Melbourne": "AU",
    "Australia/Brisbane": "AU",
    "Australia/Perth": "AU",
    "Europe/Berlin": "DE",
    "Europe/Paris": "FR",
    "Asia/Tokyo": "JP",
    "Asia/Singapore": "SG",
    "Asia/Dubai": "AE",
    "Europe/Amsterdam": "NL",
    "Europe/Zurich": "CH",
    "Europe/Stockholm": "SE",
    "Europe/Dublin": "IE",
    "Europe/Madrid": "ES",
    "Europe/Rome": "IT",
    "America/Sao_Paulo": "BR",
    "America/Mexico_City": "MX",
    "Africa/Johannesburg": "ZA",
    "Pacific/Auckland": "NZ",
}


def mask_ip(ip_str: Optional[str]) -> str:
    """
    Masks IP address for privacy in logs without exposing identifiable visitor IP.
    IPv4: 203.0.113.195 -> 203.0.***.***
    IPv6: 2001:db8:85a3:: -> 2001:db8:***
    """
    if not ip_str:
        return "none"
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        if ip.version == 4:
            parts = ip_str.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.***.***"
            return "***.***"
        else:
            parts = ip_str.split(":")
            if len(parts) >= 2:
                return f"{parts[0]}:{parts[1]}:***"
            return "***"
    except Exception:
        return "***"


def is_private_or_loopback_ip(ip_str: Optional[str]) -> bool:
    """
    Check if the given IP address string is loopback, link-local, private, or invalid.
    """
    if not ip_str:
        return True
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_reserved
            or ip.is_link_local
            or ip.is_unspecified
            or ip.is_multicast
        )
    except ValueError:
        return True


def is_trusted_proxy(ip_str: Optional[str], trusted_proxies: Optional[List[str]] = None) -> bool:
    """
    Verifies if a connecting client host is an authorized trusted reverse-proxy or CDN.
    Supports localhost, testclient, IPv4, IPv6, and CIDR ranges.
    """
    if not ip_str:
        return False
    cleaned = ip_str.strip().lower()
    if cleaned in ("testclient", "localhost", "127.0.0.1", "::1"):
        return True

    proxies = trusted_proxies or settings.trusted_proxies_list
    if cleaned in [p.lower() for p in proxies]:
        return True

    try:
        target_ip = ipaddress.ip_address(cleaned)
        for pattern in proxies:
            pattern = pattern.strip()
            if not pattern:
                continue
            try:
                if "/" in pattern:
                    if target_ip in ipaddress.ip_network(pattern, strict=False):
                        return True
                else:
                    if target_ip == ipaddress.ip_address(pattern):
                        return True
            except ValueError:
                continue
    except ValueError:
        return False
    return False


def get_client_ip_from_headers(
    headers: Dict[str, str],
    client_host: Optional[str] = None,
    trusted_proxies: Optional[List[str]] = None
) -> Optional[str]:
    """
    Extracts the genuine public IP address of the visitor.
    Forwarded headers are ONLY trusted when the direct connecting host is verified
    against the configured trusted proxy infrastructure.
    """
    # 1. If direct host is a verified trusted proxy, inspect forwarded headers
    if is_trusted_proxy(client_host, trusted_proxies):
        # Cloudflare / reverse proxy headers
        for h in ["cf-connecting-ip", "x-real-ip"]:
            val = headers.get(h)
            if val:
                candidate = val.split(",")[0].strip()
                if not is_private_or_loopback_ip(candidate):
                    return candidate

        # X-Forwarded-For: leftmost IP is client IP
        xff = headers.get("x-forwarded-for")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            for candidate in parts:
                if not is_private_or_loopback_ip(candidate):
                    return candidate

    # 2. If direct host is not a proxy, or if no public IP in forwarded headers:
    # Use client_host directly only if it is a valid public IP
    if client_host and not is_private_or_loopback_ip(client_host):
        return client_host

    return None


def get_country_from_headers(
    headers: Dict[str, str],
    client_host: Optional[str] = None,
    trusted_proxies: Optional[List[str]] = None
) -> Optional[str]:
    """
    Checks common CDN/proxy country headers (Cloudflare, AWS CloudFront, Fastly).
    Strictly verifies that the request arrived from a trusted proxy infrastructure.
    """
    is_trusted = is_trusted_proxy(client_host, trusted_proxies)
    if not is_trusted:
        return None

    for header_name in ["cf-ipcountry", "x-country-code", "cloudfront-viewer-country", "x-geo-country"]:
        country_code = headers.get(header_name)
        if country_code:
            code = country_code.strip().upper()
            if len(code) == 2 and code in COUNTRIES_DB and code not in ("XX", "T1"):
                return code
    return None


def get_country_from_accept_language(accept_language: Optional[str]) -> Optional[str]:
    """
    Parses Accept-Language header (e.g., 'en-US,en;q=0.9,hi-IN;q=0.8') to extract a country hint.
    """
    if not accept_language:
        return None
    try:
        tokens = accept_language.split(",")
        for token in tokens:
            lang_region = token.split(";")[0].strip()
            if "-" in lang_region:
                _, region = lang_region.split("-", 1)
                region_code = region.strip().upper()
                if len(region_code) == 2 and region_code in COUNTRIES_DB:
                    return region_code
            elif "_" in lang_region:
                _, region = lang_region.split("_", 1)
                region_code = region.strip().upper()
                if len(region_code) == 2 and region_code in COUNTRIES_DB:
                    return region_code
    except Exception:
        pass
    return None


def get_country_from_timezone(timezone: Optional[str]) -> Optional[str]:
    """
    Maps client timezone (e.g. 'Asia/Kolkata') to country code.
    """
    if not timezone:
        return None
    tz_clean = timezone.strip()
    return TIMEZONE_COUNTRY_MAP.get(tz_clean)


async def lookup_ip_geolocation(ip: str) -> Optional[Dict[str, Any]]:
    """
    Query IP geolocation API with timeout, in-memory TTL caching, and provider fallback.
    Never logs raw visitor IP addresses.
    """
    if is_private_or_loopback_ip(ip):
        return None

    now = time.time()
    if ip in _IP_CACHE:
        timestamp, cached_result = _IP_CACHE[ip]
        if now - timestamp < _CACHE_TTL_SECONDS:
            return cached_result

    # Masked IP for safe diagnostics
    masked = mask_ip(ip)

    # 1. Primary Provider: ipapi.co
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"https://ipapi.co/{ip}/json/")
            if resp.status_code == 200:
                data = resp.json()
                country = data.get("country_code") or data.get("country")
                if country and len(country) == 2:
                    code = country.upper()
                    if code in COUNTRIES_DB:
                        result = {
                            "country": code,
                            "currency": data.get("currency"),
                            "city": data.get("city"),
                            "region": data.get("region"),
                        }
                        _IP_CACHE[ip] = (now, result)
                        return result
    except Exception as e:
        logger.debug(f"Primary IP geolocation lookup failed for {masked}: {e}")

    # 2. Secondary Provider Fallback: ip-api.com
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,currency,city"
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    country = data.get("countryCode")
                    if country and len(country) == 2:
                        code = country.upper()
                        if code in COUNTRIES_DB:
                            result = {
                                "country": code,
                                "currency": data.get("currency"),
                                "city": data.get("city"),
                                "region": data.get("region"),
                            }
                            _IP_CACHE[ip] = (now, result)
                            return result
    except Exception as e:
        logger.debug(f"Secondary IP geolocation lookup failed for {masked}: {e}")

    return None


def _build_detection_result(
    country_code: str,
    detection_method: str,
    confidence: float,
    status: str = "success"
) -> Dict[str, Any]:
    """Helper to assemble a consistent RegionDetectionResponse dictionary."""
    country_meta = COUNTRIES_DB.get(country_code, COUNTRIES_DB.get("US", {}))
    currency_code = country_meta.get("currency", "USD")
    currency_meta = CURRENCIES_DB.get(
        currency_code,
        {"code": currency_code, "name": currency_code, "symbol": currency_code, "decimals": 2}
    )

    return {
        "detected": True,
        "status": status,
        "detection_method": detection_method,
        "confidence": confidence,
        "country": country_code,
        "country_name": country_meta.get("name", country_code),
        "flag": country_meta.get("flag", "🌐"),
        "suggested_currency": currency_code,
        "currency_name": currency_meta.get("name", currency_code),
        "currency_symbol": currency_meta.get("symbol", "$"),
        "decimals": currency_meta.get("decimals", 2),
        "dial_code": country_meta.get("dial_code", "+1"),
        "locale": country_meta.get("locale", "en-US"),
    }


def _build_unavailable_result() -> Dict[str, Any]:
    """Helper to return an explicit unavailable detection response."""
    return {
        "detected": False,
        "status": "unavailable",
        "detection_method": "unavailable",
        "confidence": 0.0,
        "country": None,
        "country_name": None,
        "flag": None,
        "suggested_currency": None,
        "currency_name": None,
        "currency_symbol": None,
        "decimals": 2,
        "dial_code": None,
        "locale": None,
    }


async def detect_region_info(
    headers: Dict[str, str],
    client_host: Optional[str] = None,
    timezone: Optional[str] = None,
    client_hint_country: Optional[str] = None
) -> Dict[str, Any]:
    """
    Authoritative detection pipeline with strict priority:
    1. Dev mode override (only when DEV_MODE=True and DEV_COUNTRY_OVERRIDE configured).
    2. Trusted proxy / CDN country header (CF-IPCountry, CloudFront-Viewer-Country).
    3. Actual visitor public IP geolocation (with timeout & multi-provider fallback).
    4. Browser locale (Accept-Language) as weak fallback.
    5. Browser timezone as weak fallback.
    6. Unavailable state (never claims US is a detected location).

    Note: Client-supplied hint is NEVER treated as proof of location.
    """
    # 1. Dev Mode Override (for deterministic local testing)
    if settings.DEV_MODE and settings.DEV_COUNTRY_OVERRIDE:
        dev_code = settings.DEV_COUNTRY_OVERRIDE.strip().upper()
        if dev_code in COUNTRIES_DB:
            return _build_detection_result(
                country_code=dev_code,
                detection_method="dev_override",
                confidence=1.0,
                status="dev_override"
            )

    # 2. Trusted Proxy / CDN Country Header
    header_country = get_country_from_headers(headers, client_host)
    if header_country and header_country in COUNTRIES_DB:
        return _build_detection_result(
            country_code=header_country,
            detection_method="header",
            confidence=0.95,
            status="success"
        )

    # 3. Visitor Public IP Geolocation
    client_ip = get_client_ip_from_headers(headers, client_host)
    if client_ip and not is_private_or_loopback_ip(client_ip):
        geo = await lookup_ip_geolocation(client_ip)
        if geo and geo.get("country") in COUNTRIES_DB:
            country_code = geo["country"]
            return _build_detection_result(
                country_code=country_code,
                detection_method="ip_geolocation",
                confidence=0.85,
                status="success"
            )

    # 4. Browser Locale (Weak Fallback)
    accept_lang = headers.get("accept-language")
    lang_country = get_country_from_accept_language(accept_lang)
    if lang_country and lang_country in COUNTRIES_DB:
        return _build_detection_result(
            country_code=lang_country,
            detection_method="browser_locale",
            confidence=0.60,
            status="fallback"
        )

    # 5. Browser Timezone (Weak Fallback)
    tz_country = get_country_from_timezone(timezone)
    if tz_country and tz_country in COUNTRIES_DB:
        return _build_detection_result(
            country_code=tz_country,
            detection_method="browser_timezone",
            confidence=0.55,
            status="fallback"
        )

    # 6. Client Hint (weak fallback when proxy/IP/locale did not yield a country; never overrides reliable detection)
    if client_hint_country:
        hint_code = client_hint_country.strip().upper()
        if hint_code in COUNTRIES_DB:
            return _build_detection_result(
                country_code=hint_code,
                detection_method="client_hint",
                confidence=1.0,
                status="fallback"
            )

    # 7. Detection Unavailable (Localhost / Unknown IP / No Headers)
    return _build_unavailable_result()


def list_all_countries() -> List[Dict[str, Any]]:
    """
    Returns all countries sorted with popular countries at top, followed by alphabetical order.
    """
    all_countries = list(COUNTRIES_DB.values())
    popular = [c for c in all_countries if c.get("popular")]
    others = [c for c in all_countries if not c.get("popular")]
    popular.sort(key=lambda x: x["name"])
    others.sort(key=lambda x: x["name"])
    return popular + others


def list_all_currencies() -> List[Dict[str, Any]]:
    """
    Returns all supported currencies sorted alphabetically by code.
    """
    currencies = list(CURRENCIES_DB.values())
    currencies.sort(key=lambda x: x["code"])
    return currencies
