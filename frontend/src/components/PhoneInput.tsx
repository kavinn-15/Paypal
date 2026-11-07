import React, { useState, useEffect } from 'react';
import { Phone, ChevronDown } from 'lucide-react';

export interface CountryOption {
  code: string;
  dialCode: string;
  name: string;
  flag: string;
  formatPlaceholder: string;
}

export const COUNTRIES: CountryOption[] = [
  { code: 'IN', dialCode: '+91', name: 'India', flag: '🇮🇳', formatPlaceholder: '98765 43210' },
  { code: 'US', dialCode: '+1', name: 'United States', flag: '🇺🇸', formatPlaceholder: '202 555 0123' },
  { code: 'GB', dialCode: '+44', name: 'United Kingdom', flag: '🇬🇧', formatPlaceholder: '7911 123456' },
  { code: 'CA', dialCode: '+1', name: 'Canada', flag: '🇨🇦', formatPlaceholder: '416 555 0199' },
  { code: 'AU', dialCode: '+61', name: 'Australia', flag: '🇦🇺', formatPlaceholder: '412 345 678' },
  { code: 'SG', dialCode: '+65', name: 'Singapore', flag: '🇸🇬', formatPlaceholder: '8123 4567' },
  { code: 'AE', dialCode: '+971', name: 'United Arab Emirates', flag: '🇦🇪', formatPlaceholder: '50 123 4567' },
  { code: 'DE', dialCode: '+49', name: 'Germany', flag: '🇩🇪', formatPlaceholder: '151 23456789' },
  { code: 'FR', dialCode: '+33', name: 'France', flag: '🇫🇷', formatPlaceholder: '6 12 34 56 78' },
  { code: 'JP', dialCode: '+81', name: 'Japan', flag: '🇯🇵', formatPlaceholder: '90 1234 5678' },
];

interface PhoneInputProps {
  value?: string;
  onChange: (fullNumber: string, countryCode: string, nationalNumber: string) => void;
  defaultCountryCode?: string;
  disabled?: boolean;
  required?: boolean;
  label?: string;
  error?: string;
  placeholder?: string;
}

export const PhoneInput: React.FC<PhoneInputProps> = ({
  value = '',
  onChange,
  defaultCountryCode = '+91',
  disabled = false,
  required = false,
  label = 'Mobile Phone Number',
  error,
  placeholder,
}) => {
  const [selectedCountry, setSelectedCountry] = useState<CountryOption>(() => {
    return COUNTRIES.find((c) => c.dialCode === defaultCountryCode) || COUNTRIES[0];
  });

  const [nationalNumber, setNationalNumber] = useState<string>(() => {
    if (!value) return '';
    // Strip dial code if present
    for (const c of COUNTRIES) {
      if (value.startsWith(c.dialCode)) {
        return value.slice(c.dialCode.length).trim();
      }
    }
    return value.replace(/^\+/, '').trim();
  });

  useEffect(() => {
    if (value) {
      for (const c of COUNTRIES) {
        if (value.startsWith(c.dialCode)) {
          setSelectedCountry(c);
          setNationalNumber(value.slice(c.dialCode.length).trim());
          return;
        }
      }
    }
  }, [value]);

  const handleCountryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const dialCode = e.target.value;
    const country = COUNTRIES.find((c) => c.dialCode === dialCode) || COUNTRIES[0];
    setSelectedCountry(country);
    const cleaned = nationalNumber.replace(/[^\d]/g, '');
    const full = cleaned ? `${country.dialCode}${cleaned}` : '';
    onChange(full, country.dialCode, cleaned);
  };

  const handleNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    // Allow digits and spaces
    const cleaned = raw.replace(/[^\d]/g, '');
    setNationalNumber(cleaned);
    const full = cleaned ? `${selectedCountry.dialCode}${cleaned}` : '';
    onChange(full, selectedCountry.dialCode, cleaned);
  };

  return (
    <div className="w-full">
      {label && (
        <label className="block text-xs font-semibold text-ink mb-1.5">
          {label} {required && <span className="text-rose-500">*</span>}
        </label>
      )}

      <div className="flex rounded-xl shadow-xs border border-slate-200 focus-within:border-electric focus-within:ring-2 focus-within:ring-electric/20 bg-white transition-all overflow-hidden min-h-[44px]">
        {/* Country selector dropdown */}
        <div className="relative border-r border-slate-200 bg-slate-50 flex items-center shrink-0 max-w-[105px] sm:max-w-[140px] md:max-w-none">
          <select
            value={selectedCountry.dialCode}
            onChange={handleCountryChange}
            disabled={disabled}
            className="appearance-none bg-transparent pl-2.5 sm:pl-3 pr-6 sm:pr-7 py-2.5 text-xs sm:text-sm font-semibold text-ink cursor-pointer focus:outline-none disabled:opacity-60 w-full truncate min-h-[44px]"
            title="Select country code"
          >
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.dialCode}>
                {c.flag} {c.dialCode} ({c.name})
              </option>
            ))}
          </select>
          <ChevronDown className="w-3.5 h-3.5 text-sardine-slate absolute right-1.5 sm:right-2 pointer-events-none" />
        </div>

        {/* National Number Input */}
        <div className="relative flex-1 flex items-center min-w-0">
          <div className="absolute inset-y-0 left-0 pl-2.5 sm:pl-3 flex items-center pointer-events-none text-slate-400">
            <Phone className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
          </div>
          <input
            type="tel"
            inputMode="numeric"
            value={nationalNumber}
            onChange={handleNumberChange}
            disabled={disabled}
            placeholder={placeholder || selectedCountry.formatPlaceholder}
            className="w-full pl-8 sm:pl-9 pr-3 py-2.5 text-xs sm:text-sm font-mono text-ink placeholder:text-slate-400 focus:outline-none bg-transparent disabled:opacity-60 min-h-[44px]"
          />
        </div>
      </div>

      {error ? (
        <p className="mt-1 text-xs text-rose-600 font-medium">{error}</p>
      ) : (
        <p className="mt-1 text-[11px] text-sardine-slate">
          E.164 format: <span className="font-mono text-slate-600">{selectedCountry.dialCode} {nationalNumber || '...'}</span>
        </p>
      )}
    </div>
  );
};

