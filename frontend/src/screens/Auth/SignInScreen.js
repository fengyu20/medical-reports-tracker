// src/screens/Auth/SignInScreen.js
import React, { useEffect } from 'react';
import { authService } from '../../services/authService';
import Header from '../../components/Header/Header';

export default function SignInScreen() {
  useEffect(() => {
    // Use localhost instead of 127.0.0.1
    window.location.href = 'http://localhost:5001/auth/login';
  }, []);

  // Return empty or loading state since we're redirecting immediately
  return (
    <div className="container">
      <h1>Redirecting to login...</h1>
    </div>
  );
}