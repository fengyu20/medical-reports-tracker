// frontend/src/components/Header/Header.js

import React from 'react';
import { Link } from 'react-router-dom';
import SignOutButton from '../../screens/Auth/SignOutButton';
import './Header.css';

const Header = () => {
  return (
    <header className="header">
      <div className="header-content">
        <nav className="nav-links">
          <Link to="/home" className="nav-link">Home</Link>
          <Link to="/upload" className="nav-link">Upload</Link>
          <SignOutButton />
        </nav>
      </div>
    </header>
  );
};

export default Header;