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
