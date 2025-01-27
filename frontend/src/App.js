// frontend/src/App.js
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate} from 'react-router-dom';
import './App.css';
import { AuthProvider } from './contexts/AuthContext'; 
import Header from './components/Header/Header';

// Screens
import SignInScreen from './screens/Auth/SignInScreen';
import HomeScreen from './screens/Home/HomeScreen';
import UploadScreen from './screens/Upload/UploadScreen';
import ReviewScreen from './screens/Review/ReviewScreen';

function App() {
  return (
    <Router>
      <AuthProvider>
        <Header />
        <Routes>
          <Route path="/home" element={<HomeScreen />} />
          <Route path="/upload" element={<UploadScreen />} />
          <Route path="/review" element={<ReviewScreen />} />
          <Route path="/auth" element={<SignInScreen />} />
          <Route path="/review" element={<ReviewScreen />} />
          <Route path="/signin" element={<SignInScreen />} />
          <Route path="/" element={<Navigate to="/signin" replace />} />
          <Route path="*" element={<Navigate to="/signin" replace />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}

export default App;