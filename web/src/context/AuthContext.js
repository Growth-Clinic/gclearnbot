import React, { createContext, useState, useContext, useEffect } from 'react';
import { AuthService } from '../services/auth';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const user = AuthService.getCurrentUser();
    if (user) {
      setUser(user);
    }
    setLoading(false);
  }, []);

  const value = {
    user,
    loading,
    login: async (email, password) => {
      const userData = await AuthService.login(email, password);
      setUser(userData);
    },
    logout: () => {
      AuthService.logout();
      setUser(null);
    },
    register: AuthService.register
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
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