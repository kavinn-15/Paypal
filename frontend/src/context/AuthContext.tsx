import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, getStoredToken, clearStoredTokens } from '../api/client';
import { UserProfile } from '../types';

interface AuthContextType {
  currentUser: UserProfile | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isEmailVerified: boolean;
  isPhoneVerified: boolean;
  login: (email: string, password: string) => Promise<any>;
  loginWithPhonePassword: (phoneNumber: string, password: string) => Promise<any>;
  loginWithPhoneOtp: (phoneNumber: string, otp: string) => Promise<any>;
  demoLogin: () => Promise<any>;
  register: (data: {
    name: string;
    email: string;
    password: string;
    phone_number?: string;
    phone_country_code?: string;
    currency?: string;
    preferred_currency?: string;
    country?: string;
    business_type?: string;
  }) => Promise<any>;
  verifyEmailOtp: (email: string, otp: string) => Promise<any>;
  resendVerificationOtp: (email: string) => Promise<any>;
  verifyPhoneOtp: (phoneNumber: string, otp: string) => Promise<any>;
  resendPhoneOtp: (phoneNumber: string) => Promise<any>;
  loginWithGoogleToken: (credential: string) => Promise<any>;
  loginWithGoogleCode: (code: string, state?: string) => Promise<any>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshUser = async () => {
    const token = getStoredToken();
    if (!token) {
      setCurrentUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const user = await api.getCurrentUser();
      setCurrentUser(user);
    } catch {
      clearStoredTokens();
      setCurrentUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await api.login(email, password);
      await refreshUser();
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const demoLogin = async () => {
    setIsLoading(true);
    try {
      const res = await api.demoLogin();
      await refreshUser();
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const loginWithPhonePassword = async (phoneNumber: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await api.loginWithPhonePassword(phoneNumber, password);
      await refreshUser();
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const loginWithPhoneOtp = async (phoneNumber: string, otp: string) => {
    setIsLoading(true);
    try {
      const res = await api.verifyPhoneLoginOtp(phoneNumber, otp);
      await refreshUser();
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (data: {
    name: string;
    email: string;
    password: string;
    phone_number?: string;
    phone_country_code?: string;
    currency?: string;
    preferred_currency?: string;
    country?: string;
    business_type?: string;
  }) => {
    setIsLoading(true);
    try {
      const res = await api.register(data);
      await refreshUser();
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const verifyEmailOtp = async (email: string, otp: string) => {
    setIsLoading(true);
    try {
      const res = await api.verifyEmailOtp(email, otp);
      await refreshUser();
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const resendVerificationOtp = async (email: string) => {
    return api.resendVerificationOtp(email);
  };

  const verifyPhoneOtp = async (phoneNumber: string, otp: string) => {
    setIsLoading(true);
    try {
      const res = await api.verifyPhoneOtp(phoneNumber, otp);
      await refreshUser();
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const resendPhoneOtp = async (phoneNumber: string) => {
    return api.resendPhoneOtp(phoneNumber);
  };

  const loginWithGoogleToken = async (credential: string) => {
    setIsLoading(true);
    try {
      const res = await api.submitGoogleToken(credential);
      await refreshUser();
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const loginWithGoogleCode = async (code: string, state?: string) => {
    setIsLoading(true);
    try {
      const res = await api.completeGoogleCallback(code, state);
      await refreshUser();
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await api.logout();
    } finally {
      setCurrentUser(null);
      setIsLoading(false);
    }
  };

  const isEmailVerified = Boolean(
    currentUser && (currentUser.is_demo || currentUser.email_verified === true)
  );

  const isPhoneVerified = Boolean(
    currentUser && (currentUser.is_demo || currentUser.phone_verified === true)
  );

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        isLoading,
        isAuthenticated: !!currentUser,
        isEmailVerified,
        isPhoneVerified,
        login,
        loginWithPhonePassword,
        loginWithPhoneOtp,
        demoLogin,
        register,
        verifyEmailOtp,
        resendVerificationOtp,
        verifyPhoneOtp,
        resendPhoneOtp,
        loginWithGoogleToken,
        loginWithGoogleCode,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

