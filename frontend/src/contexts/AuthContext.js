// frontend/src/contexts/AuthContext.js
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const checkAuthStatus = useCallback(async () => {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const authCode = urlParams.get('code');

      if (authCode && !isAuthenticated) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        setIsAuthenticated(true);
        window.history.replaceState({}, document.title, '/');
        setIsLoading(false);
        return;
      }

      if (isAuthenticated) {
        setIsLoading(false);
        return;
      }

      const checkResponse = await fetch('http://localhost:5001/auth/check-session', {
        credentials: 'include',
        headers: {
          'Accept': 'application/json'
        }
      });

      if (checkResponse.ok) {
        setIsAuthenticated(true);
        if (location.pathname === '/signin') {
          navigate('/');
        }
      } else {
        setIsAuthenticated(false);
        if (!location.pathname.includes('/signin')) {
          navigate('/signin');
        }
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setIsAuthenticated(false);
      if (!location.pathname.includes('/signin')) {
        navigate('/signin');
      }
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, navigate, location.pathname]);

  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);
// frontend/src/contexts/AuthContext.js

const signOut = () => {
  // Clear authentication state
  setIsAuthenticated(false);
  
  // Clear local storage and session
  localStorage.clear();
  sessionStorage.clear();
  
  // Redirect the browser to the backend's logout endpoint
  window.location.href = '/auth/logout';
};

  const value = {
    isAuthenticated,
    isLoading,
    signOut
  };

  return (
    <AuthContext.Provider value={value}>
      {!isLoading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};