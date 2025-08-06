import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { config } from '../config';
import { ApiChild, ApiInteraction, ApiSafetyAlert } from '../types';
import { SecureStorage } from './SecureStorageService';

// Base URL for the FastAPI backend - NO MOCK DATA
const BASE_URL = config.API_BASE_URL;

console.log('🔗 API Service connecting to REAL Backend:', BASE_URL);

// Security validation for production
if (config.security.enforceHTTPS && !BASE_URL.startsWith('https://')) {
  console.error('🚨 SECURITY ERROR: API must use HTTPS in production!');
  throw new Error('Production API must use HTTPS');
}

// Create axios instance for REAL API calls with security settings
const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-App-Version': config.app.version,
    'X-Environment': config.app.environment,
  },
  timeout: config.security.apiTimeout,
  // Additional security headers
  ...(config.security.enforceHTTPS && {
    httpsAgent: undefined, // Will use secure defaults
  }),
});

// Add auth token to requests
api.interceptors.request.use(
  async (config) => {
    const token = await SecureStorage.getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    console.log('🚀 REAL API Request:', config.method?.toUpperCase(), config.url, config.data);
    
    return config;
  },
  (error) => {
    console.error('❌ Request Error:', error);
    return Promise.reject(error);
  }
);

// Handle responses and errors from REAL API
api.interceptors.response.use(
  (response) => {
    console.log('✅ REAL API Response:', response.status, response.config.url, response.data);
    return response;
  },
  async (error) => {
    console.error('❌ REAL API Error:', {
      status: error.response?.status,
      url: error.config?.url,
      message: error.message,
      data: error.response?.data,
      stack: error.stack
    });
    
    // Handle authentication errors
    if (error.response?.status === 401) {
      await SecureStorage.removeToken();
      AsyncStorage.removeItem('user');
    }
    
    return Promise.reject(error);
  }
);

// API Interfaces
export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    name: string;
  };
}

// REAL API Service - NO MOCK DATA
export class ApiService {
  // Authentication with REAL Backend
  static async login(credentials: LoginCredentials): Promise<LoginResponse> {
    try {
      console.log('🔐 Attempting REAL login to Backend...');
      const response = await api.post(config.endpoints.login, credentials);
      
      // Store token securely from REAL API response
      if (response.data.access_token) {
        await SecureStorage.setToken(response.data.access_token);
        await AsyncStorage.setItem('user', JSON.stringify(response.data.user));
      }
      
      return response.data;
    } catch (error) {
      console.error('❌ REAL Login failed:', error);
      throw error;
    }
  }

  // Child management methods using axios
  static async updateChild(childId: string, childData: any): Promise<ApiChild> {
    try {
      console.log('📝 Updating child in REAL Backend:', childId);
      const response = await api.put(`${config.endpoints.children}/${childId}`, childData);
      return response.data;
    } catch (error) {
      console.error('❌ Failed to update child in REAL Backend:', error);
      throw error;
    }
  }

  static async deleteChild(childId: string): Promise<void> {
    try {
      console.log('🗑️ Deleting child from REAL Backend:', childId);
      await api.delete(`${config.endpoints.children}/${childId}`);
    } catch (error) {
      console.error('❌ Failed to delete child from REAL Backend:', error);
      throw error;
    }
  }

  static async logout(): Promise<void> {
    try {
      console.log('🚪 Logging out from REAL Backend...');
      await api.post(config.endpoints.logout);
    } catch (error) {
      console.error('❌ Logout error:', error);
    } finally {
      await SecureStorage.removeToken();
      await AsyncStorage.removeItem('user');
    }
  }

  // Children management from REAL Backend
  static async getChildren(): Promise<ApiChild[]> {
    try {
      console.log('👶 Fetching children from REAL Backend...');
      const response = await api.get(config.endpoints.children);
      return response.data.children || response.data;
    } catch (error) {
      console.error('❌ Failed to fetch children from REAL Backend:', error);
      throw error;
    }
  }

  static async getChild(childId: string): Promise<ApiChild> {
    try {
      console.log('👶 Fetching child details from REAL Backend:', childId);
      const response = await api.get(`${config.endpoints.children}/${childId}`);
      return response.data;
    } catch (error) {
      console.error('❌ Failed to fetch child from REAL Backend:', error);
      throw error;
    }
  }

  // Interactions from REAL Backend
  static async getChildInteractions(childId: string, limit: number = 10): Promise<ApiInteraction[]> {
    try {
      console.log('💬 Fetching interactions from REAL Backend for child:', childId);
      const endpoint = config.endpoints.interactions.replace('{childId}', childId);
      const response = await api.get(`${endpoint}?limit=${limit}`);
      return response.data.interactions || response.data;
    } catch (error) {
      console.error('❌ Failed to fetch interactions from REAL Backend:', error);
      throw error;
    }
  }

  // Safety alerts from REAL Backend
  static async getSafetyAlerts(): Promise<ApiSafetyAlert[]> {
    try {
      console.log('⚠️ Fetching safety alerts from REAL Backend...');
      const response = await api.get(config.endpoints.safetyAlerts);
      return response.data.alerts || response.data;
    } catch (error) {
      console.error('❌ Failed to fetch safety alerts from REAL Backend:', error);
      throw error;
    }
  }

  static async markSafetyAlertAsResolved(alertId: string): Promise<void> {
    try {
      console.log('✅ Marking safety alert as resolved:', alertId);
      await api.patch(`${config.endpoints.safetyAlerts}/${alertId}/resolve`);
    } catch (error) {
      console.error('❌ Failed to resolve safety alert:', error);
      throw error;
    }
  }

  // Push notification token management
  static async registerPushToken(tokenData: {
    token: string;
    platform: string;
    deviceId: string;
    appVersion: string;
  }): Promise<void> {
    try {
      console.log('📱 Registering push token with backend...');
      await api.post('/api/notifications/register-token', tokenData);
    } catch (error) {
      console.error('❌ Failed to register push token:', error);
      throw error;
    }
  }

  static async unregisterPushToken(token: string): Promise<void> {
    try {
      console.log('📱 Unregistering push token from backend...');
      await api.delete('/api/notifications/unregister-token', { data: { token } });
    } catch (error) {
      console.error('❌ Failed to unregister push token:', error);
      throw error;
    }
  }

  // Health check for REAL Backend
  static async healthCheck(): Promise<boolean> {
    try {
      console.log('🏥 Checking REAL Backend health...');
      const response = await api.get('/health');
      return response.status === 200;
    } catch (error) {
      console.error('❌ REAL Backend health check failed:', error);
      return false;
    }
  }
}

export default ApiService;
