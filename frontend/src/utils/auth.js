import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  }
});

export const checkSession = async () => {
  try {
    const response = await api.get('/auth/check-session');
    return response.data;
  } catch (error) {
    console.error('Session check error:', error);
    if (error.response?.status === 401) {
      return { authenticated: false };
    }
    if (error.code === 'ERR_NETWORK') {
      console.error('Network error - API might be down');
      return { authenticated: false, error: 'API_UNAVAILABLE' };
    }
    return { authenticated: false, error: error.message };
  }
};

export const handleLogin = () => {
  const loginUrl = `${API_URL}/auth/login`;
  console.log('Redirecting to:', loginUrl);
  window.location.href = loginUrl;
};

export const handleLogout = async () => {
  try {
    await api.get('/auth/logout');
    window.location.href = '/signin';
  } catch (error) {
    console.error('Logout failed:', error);
    window.location.href = '/signin';
  }
}; 