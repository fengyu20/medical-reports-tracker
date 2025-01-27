const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

export const authService = {
  login: async () => {
    window.location.href = `${API_URL}/login`;
  },

  logout: async () => {
    window.location.href = `${API_URL}/logout`;
  },

  getCurrentUser: async () => {
    try {
      const response = await fetch(`${API_URL}/current_user`, {
        credentials: 'include' // Important for cookies
      });
      if (!response.ok) throw new Error('Not authenticated');
      return await response.json();
    } catch (error) {
      return null;
    }
  }
};