// frontend/src/screens/Auth/SignOutButton.js

import React from 'react';
import { useAuth } from '../../contexts/AuthContext';
import './SignOutButton.css';

const SignOutButton = () => {
  // Destructure the signOut method from the AuthContext
  const { signOut } = useAuth();

  const handleSignOut = async () => {
    try {
      // Call the signOut function provided by AuthContext
      await signOut();
      // You can add any post-logout logic here if needed
    } catch (error) {
      console.error('Sign out failed:', error);
    }
  };

  return (
    <button onClick={handleSignOut} className="sign-out-button">
      Sign Out
    </button>
  );
};

export default SignOutButton;