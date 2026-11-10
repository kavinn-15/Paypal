import { describe, it, expect, beforeEach } from 'vitest';
import { getStoredToken, getStoredRefreshToken, setStoredTokens, clearStoredTokens } from './api/client';

// Simple polyfill for node test environment
const mockStorage = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(globalThis, 'localStorage', {
  value: mockStorage,
  writable: true,
});

describe('Auth Token Storage Security', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('stores and retrieves access and refresh tokens correctly', () => {
    expect(getStoredToken()).toBeNull();
    expect(getStoredRefreshToken()).toBeNull();

    setStoredTokens('test-access-token-123', 'test-refresh-token-456');

    expect(getStoredToken()).toBe('test-access-token-123');
    expect(getStoredRefreshToken()).toBe('test-refresh-token-456');
  });

  it('clears stored tokens completely on logout', () => {
    setStoredTokens('access-token', 'refresh-token');
    localStorage.setItem('cashflow_user_email', 'user@test.org');

    clearStoredTokens();

    expect(getStoredToken()).toBeNull();
    expect(getStoredRefreshToken()).toBeNull();
    expect(localStorage.getItem('cashflow_user_email')).toBeNull();
  });
});

describe('Password Validation Logic', () => {
  const evaluatePassword = (password: string) => {
    let score = 0;
    if (password.length >= 8) score += 1;
    if (/[A-Z]/.test(password)) score += 1;
    if (/[0-9]/.test(password)) score += 1;
    if (/[^A-Za-z0-9]/.test(password)) score += 1;
    return score;
  };

  it('scores weak passwords appropriately', () => {
    expect(evaluatePassword('short')).toBe(0);
    expect(evaluatePassword('onlyletters')).toBe(1);
  });

  it('scores strong passwords with mixed characters', () => {
    expect(evaluatePassword('StrongPass1!')).toBe(4);
    expect(evaluatePassword('DecentPass1')).toBe(3);
  });
});

describe('OTP & Security Helpers', () => {
  const maskEmail = (val: string) => {
    if (!val || !val.includes('@')) return val;
    const [name, domain] = val.split('@');
    if (name.length <= 2) return `${name}***@${domain}`;
    return `${name[0]}***${name[name.length - 1]}@${domain}`;
  };

  const cleanOtpInput = (raw: string) => {
    return raw.replace(/\D/g, '').slice(0, 6);
  };

  it('masks emails to protect user privacy', () => {
    expect(maskEmail('alex@example.com')).toBe('a***x@example.com');
    expect(maskEmail('ed@company.org')).toBe('ed***@company.org');
    expect(maskEmail('security-lead@fintech.io')).toBe('s***d@fintech.io');
  });

  it('sanitizes and constrains OTP code digits', () => {
    expect(cleanOtpInput('12a3b4c5d6e7f')).toBe('123456');
    expect(cleanOtpInput(' 9 8 7 6 5 4 ')).toBe('987654');
    expect(cleanOtpInput('123')).toBe('123');
  });
});

describe('Phone Number & SMS Auth Logic', () => {
  const maskPhone = (val: string) => {
    if (!val || val.length < 8) return val;
    const prefix = val.slice(0, 4);
    const suffix = val.slice(-3);
    return `${prefix}*** ***${suffix}`;
  };

  const sanitizeNationalNumber = (raw: string) => {
    return raw.replace(/[^\d]/g, '');
  };

  const buildE164Number = (dialCode: string, national: string) => {
    const cleaned = sanitizeNationalNumber(national);
    if (!cleaned) return '';
    return `${dialCode}${cleaned}`;
  };

  it('masks phone numbers correctly to protect identity', () => {
    expect(maskPhone('+919876543210')).toBe('+919*** ***210');
    expect(maskPhone('+12025550123')).toBe('+120*** ***123');
  });

  it('builds canonical E.164 phone numbers with India dial code default', () => {
    expect(buildE164Number('+91', '98765 43210')).toBe('+919876543210');
    expect(buildE164Number('+1', '(202) 555-0123')).toBe('+12025550123');
    expect(buildE164Number('+44', '7911 123456')).toBe('+447911123456');
  });

  it('handles empty or whitespace phone inputs safely', () => {
    expect(buildE164Number('+91', '   ')).toBe('');
    expect(sanitizeNationalNumber('')).toBe('');
  });
});

describe('Navigation Route Redirection & Aliasing', () => {
  const isNavPathActive = (itemId: string, pathname: string) => {
    if (itemId === 'dashboard') {
      return (
        pathname === '/' ||
        pathname === '/dashboard' ||
        pathname === '/forecast' ||
        pathname === '/obligations' ||
        pathname === '/plans'
      );
    }
    if (itemId === 'whatif') {
      return pathname === '/whatif' || pathname === '/what-if';
    }
    if (itemId === 'supervisor') {
      return pathname === '/supervisor';
    }
    if (itemId === 'negotiation') {
      return pathname === '/negotiation' || pathname === '/negotiations';
    }
    if (itemId === 'resilience') {
      return pathname === '/resilience';
    }
    if (itemId === 'timeline') {
      return pathname === '/timeline';
    }
    if (itemId === 'clients') {
      return pathname === '/clients' || pathname === '/invoices';
    }
    if (itemId === 'inbox') {
      return pathname === '/inbox' || pathname === '/approvals';
    }
    if (itemId === 'audit') {
      return pathname === '/audit';
    }
    if (itemId === 'settings') {
      return pathname === '/settings' || pathname === '/setting';
    }
    return false;
  };

  it('correctly resolves and highlights all core application routes and aliases', () => {
    expect(isNavPathActive('whatif', '/whatif')).toBe(true);
    expect(isNavPathActive('whatif', '/what-if')).toBe(true);
    expect(isNavPathActive('supervisor', '/supervisor')).toBe(true);
    expect(isNavPathActive('negotiation', '/negotiation')).toBe(true);
    expect(isNavPathActive('negotiation', '/negotiations')).toBe(true);
    expect(isNavPathActive('resilience', '/resilience')).toBe(true);
    expect(isNavPathActive('timeline', '/timeline')).toBe(true);
    expect(isNavPathActive('clients', '/clients')).toBe(true);
    expect(isNavPathActive('clients', '/invoices')).toBe(true);
    expect(isNavPathActive('inbox', '/inbox')).toBe(true);
    expect(isNavPathActive('inbox', '/approvals')).toBe(true);
    expect(isNavPathActive('audit', '/audit')).toBe(true);
    expect(isNavPathActive('settings', '/settings')).toBe(true);
    expect(isNavPathActive('settings', '/setting')).toBe(true);
    expect(isNavPathActive('dashboard', '/dashboard')).toBe(true);
    expect(isNavPathActive('dashboard', '/forecast')).toBe(true);
  });
});
