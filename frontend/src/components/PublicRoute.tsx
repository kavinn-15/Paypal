import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2 } from 'lucide-react';

interface PublicRouteProps {
  children?: React.ReactNode;
}

export const PublicRoute: React.FC<PublicRouteProps> = ({ children }) => {
  const { isAuthenticated, isEmailVerified, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-ink-950 flex flex-col items-center justify-center p-4">
        <div className="flex flex-col items-center space-y-3">
          <Loader2 className="w-8 h-8 text-electric animate-spin" />
          <p className="text-xs font-mono uppercase tracking-wider text-sardine-muted">
            Checking authentication...
          </p>
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    if (!isEmailVerified) {
      return <Navigate to="/verify-email" replace />;
    }
    return <Navigate to="/dashboard" replace />;
  }

  return children ? <>{children}</> : null;
};

