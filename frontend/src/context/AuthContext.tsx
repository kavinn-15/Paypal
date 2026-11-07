import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, getStoredToken, clearStoredTokens } from '../api/client';
import { UserProfile } from '../types';

interface AuthContextType {
  currentUser: UserProfile | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<any>;
  demoLogin: () => Promise<any>;
  register: (data: {
    name: string;
    email: string;
    password: string;
    currency?: string;
    preferred_currency?: string;
    country?: string;
    business_type?: string;
  }) => Promise<any>;
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

  const register = async (data: {
    name: string;
    email: string;
    password: string;
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

  const logout = async () => {
    setIsLoading(true);
    try {
      await api.logout();
    } finally {
      setCurrentUser(null);
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        isLoading,
        isAuthenticated: !!currentUser,
        login,
        demoLogin,
        register,
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

