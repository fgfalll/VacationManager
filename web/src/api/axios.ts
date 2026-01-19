import axios from 'axios';
import { message } from 'antd';

const API_BASE_URL = '/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle errors and token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token } = response.data;
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', refresh_token);

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      }
    }

    const errorData = error.response?.data;
    let errorMessage = 'An error occurred';
    if (typeof errorData?.detail === 'string') {
      errorMessage = errorData.detail;
    } else if (typeof errorData?.message === 'string') {
      errorMessage = errorData.message;
    } else if (Array.isArray(errorData?.detail)) {
      errorMessage = errorData.detail.map((e: any) => e.msg || JSON.stringify(e)).join(', ');
    } else if (typeof errorData?.detail === 'object') {
      errorMessage = 'Validation error';
    }
    message.error(errorMessage);

    return Promise.reject(error);
  }
);

export default apiClient;
