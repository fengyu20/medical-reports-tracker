import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkSession } from '../../utils/auth';
import './SignInScreen.css';
import Header from '../../components/Header/Header';

const SignInScreen = () => {
  const navigate = useNavigate();
  const [error, setError] = useState(null);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const { authenticated, error } = await checkSession();
        if (authenticated) {
          navigate('/upload');
        } else if (error === 'API_UNAVAILABLE') {
          setError('Unable to connect to the server. Please try again later.');
        }
      } catch (err) {
        console.error('Auth check failed:', err);
        setError('Authentication service is currently unavailable.');
      }
    };
    checkAuth();
  }, [navigate]);

  const handleSignIn = async () => {
    try {
      const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';
      window.location.href = `${API_URL}/auth/login`;
    } catch (error) {
      console.error('Sign in failed:', error);
      setError('Failed to initiate sign in. Please try again.');
    }
  };

  return (
    <div className="signin-container">
      <div className="signin-box">
        <h1>Welcome Back</h1>
        <p>Please sign in to continue</p>
        {error && <div className="error-message">{error}</div>}
        <button 
          className="signin-button"
          onClick={handleSignIn}
        >
          Sign in with Cognito
        </button>
      </div>
    </div>
  );
};

export default SignInScreen;