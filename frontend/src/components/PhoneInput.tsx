import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Phone, ChevronDown, Check, Search } from 'lucide-react';

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
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const [selectedCountry, setSelectedCountry] = useState<CountryOption>(() => {
    return COUNTRIES.find((c) => c.dialCode === defaultCountryCode) || COUNTRIES[0];
  });

  const [nationalNumber, setNationalNumber] = useState<string>(() => {
    if (!value) return '';
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

  // Click outside to close custom dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearchQuery('');
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      // Auto-focus search input when opened
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
        setSearchQuery('');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const filteredCountries = useMemo(() => {
    if (!searchQuery.trim()) return COUNTRIES;
    const q = searchQuery.toLowerCase().trim();
    return COUNTRIES.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.dialCode.includes(q) ||
        c.code.toLowerCase().includes(q)
    );
  }, [searchQuery]);

  const handleSelectCountry = (country: CountryOption) => {
    setSelectedCountry(country);
    setIsOpen(false);
    setSearchQuery('');
    const cleaned = nationalNumber.replace(/[^\d]/g, '');
    const full = cleaned ? `${country.dialCode}${cleaned}` : '';
    onChange(full, country.dialCode, cleaned);
  };

  const handleNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    const cleaned = raw.replace(/[^\d]/g, '');
    setNationalNumber(cleaned);
    const full = cleaned ? `${selectedCountry.dialCode}${cleaned}` : '';
    onChange(full, selectedCountry.dialCode, cleaned);
  };

  return (
    <div className="w-full relative" ref={dropdownRef}>
      {label && (
        <label className="block text-xs font-semibold text-[var(--tx)] mb-1.5">
          {label} {required && <span className="text-[var(--r)]">*</span>}
        </label>
      )}

      <div className="flex rounded-xl shadow-xs border border-[var(--line)] focus-within:border-[var(--o1)] focus-within:ring-2 focus-within:ring-[var(--o1)]/20 bg-[var(--bg)] transition-all min-h-[44px]">
        {/* Custom Country Selector Trigger Button */}
        <div className="relative border-r border-[var(--line)] bg-[var(--side)] flex items-center shrink-0">
          <button
            type="button"
            onClick={() => !disabled && setIsOpen(!isOpen)}
            disabled={disabled}
            aria-haspopup="listbox"
            aria-expanded={isOpen}
            className="flex items-center gap-1.5 px-3 py-2.5 text-xs sm:text-sm font-semibold text-[var(--tx)] hover:bg-[var(--card2)]/50 focus:outline-none transition-colors cursor-pointer min-h-[44px] select-none"
            title="Select country code"
          >
            <span className="text-base leading-none">{selectedCountry.flag}</span>
            <span className="font-mono text-[var(--tx)]">{selectedCountry.dialCode}</span>
            <ChevronDown className={`w-3.5 h-3.5 text-[var(--mu)] transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
          </button>

          {/* Custom Dropdown Menu with High Contrast and Search */}
          {isOpen && (
            <div
              role="listbox"
              className="absolute top-[calc(100%+6px)] left-0 w-72 max-h-72 overflow-hidden rounded-xl bg-[var(--card)] border border-[var(--line)] shadow-2xl z-50 flex flex-col py-1.5 text-[var(--tx)]"
              style={{
                backgroundColor: 'var(--card)',
                color: 'var(--tx)',
                borderColor: 'var(--line)',
              }}
            >
              {/* Quick Search */}
              <div className="px-2.5 pb-2 pt-1 border-b border-[var(--line)]">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-[var(--dim)] absolute left-2.5 top-2.5 pointer-events-none" />
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search country or code..."
                    className="w-full pl-8 pr-2.5 py-1.5 text-xs rounded-lg bg-[var(--bg)] border border-[var(--line)] text-[var(--tx)] placeholder:text-[var(--dim)] focus:outline-none focus:border-[var(--o1)]"
                    style={{
                      backgroundColor: 'var(--bg)',
                      color: 'var(--tx)',
                    }}
                  />
                </div>
              </div>

              {/* Options List */}
              <div className="overflow-y-auto max-h-56 divide-y divide-[var(--line)]/30">
                {filteredCountries.length > 0 ? (
                  filteredCountries.map((c) => {
                    const isSelected = c.dialCode === selectedCountry.dialCode && c.code === selectedCountry.code;
                    return (
                      <button
                        key={c.code}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => handleSelectCountry(c)}
                        className={`w-full flex items-center justify-between px-3 py-2 text-left text-xs sm:text-sm transition-colors cursor-pointer ${
                          isSelected
                            ? 'bg-[var(--o1)]/15 text-[var(--o1)] font-semibold'
                            : 'text-[var(--tx)] hover:bg-[var(--card2)]'
                        }`}
                        style={{
                          color: isSelected ? 'var(--o1)' : 'var(--tx)',
                        }}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-base shrink-0">{c.flag}</span>
                          <span className="truncate">{c.name}</span>
                          <span className="text-[10px] text-[var(--dim)] font-mono uppercase">({c.code})</span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0 ml-2">
                          <span className="font-mono text-xs font-semibold px-1.5 py-0.5 rounded bg-[var(--side)] border border-[var(--line)]">
                            {c.dialCode}
                          </span>
                          {isSelected && <Check className="w-3.5 h-3.5 text-[var(--o1)] shrink-0" />}
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div className="px-3 py-4 text-center text-xs text-[var(--dim)]">
                    No country found matching "{searchQuery}"
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* National Number Input */}
        <div className="relative flex-1 flex items-center min-w-0 bg-[var(--bg)]">
          <div className="absolute inset-y-0 left-0 pl-2.5 sm:pl-3 flex items-center pointer-events-none text-[var(--dim)]">
            <Phone className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
          </div>
          <input
            type="tel"
            inputMode="numeric"
            value={nationalNumber}
            onChange={handleNumberChange}
            disabled={disabled}
            placeholder={placeholder || selectedCountry.formatPlaceholder}
            className="w-full pl-8 sm:pl-9 pr-3 py-2.5 text-xs sm:text-sm font-mono text-[var(--tx)] placeholder:text-[var(--dim)] focus:outline-none bg-transparent disabled:opacity-60 min-h-[44px]"
            style={{ color: 'var(--tx)' }}
          />
        </div>
      </div>

      {error ? (
        <p className="mt-1 text-xs text-[var(--r)] font-medium">{error}</p>
      ) : (
        <p className="mt-1 text-[11px] text-[var(--mu)]">
          E.164 format: <span className="font-mono text-[var(--tx)]">{selectedCountry.dialCode} {nationalNumber || '...'}</span>
        </p>
      )}
    </div>
  );
};
