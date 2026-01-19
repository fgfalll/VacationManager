import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, LoginRequest, LoginResponse } from '../api/types';
import apiClient from '../api/axios';
import { endpoints } from '../api/endpoints';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (credentials: LoginRequest) => {
        set({ isLoading: true });
        try {
          const response = await apiClient.post<LoginResponse>(
            endpoints.auth.login,
            credentials
          );
          const { access_token, refresh_token, user } = response.data;

          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', refresh_token);

          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        try {
          await apiClient.post(endpoints.auth.logout);
        } catch (error) {
          // Continue with local logout even if API call fails
        } finally {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          set({ user: null, isAuthenticated: false });
        }
      },

      checkAuth: async () => {
        const token = localStorage.getItem('access_token');
        if (!token) {
          set({ isAuthenticated: false, user: null });
          return;
        }

        try {
          const response = await apiClient.get<User>(endpoints.auth.me);
          set({
            user: response.data,
            isAuthenticated: true,
          });
        } catch (error) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          set({ user: null, isAuthenticated: false });
        }
      },

      clearError: () => {},
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// Helper function to check if user has required role
export const hasRole = (user: User | null, roles: User['role'][]): boolean => {
  if (!user) return false;
  return roles.includes(user.role);
};

// Helper function to check if user is admin
export const isAdmin = (user: User | null): boolean => {
  return user?.role === 'admin';
};

// Helper function to check if user is HR
export const isHR = (user: User | null): boolean => {
  return user?.role === 'hr';
};

// Helper function to check if user is employee (not admin or HR)
export const isEmployee = (user: User | null): boolean => {
  return user?.role === 'employee';
};
