import Constants from 'expo-constants';

/**
 * Production-Ready Configuration System
 * 
 * Features:
 * - Environment-based configuration
 * - HTTPS enforcement for production
 * - Secure defaults
 * - Runtime environment detection
 */

interface AppConfig {
  API_BASE_URL: string;
  WS_BASE_URL: string;
  endpoints: {
    login: string;
    logout: string;
    children: string;
    interactions: string;
    safetyAlerts: string;
  };
  app: {
    name: string;
    version: string;
    environment: string;
    projectId: string;
    maxInteractions: number;
    refreshInterval: number;
  };
  security: {
    enableSSLPinning: boolean;
    apiTimeout: number;
    enforceHTTPS: boolean;
  };
  features: {
    enablePushNotifications: boolean;
    enableAnalytics: boolean;
    enableCrashReporting: boolean;
  };
  colors: {
    primary: string;
    secondary: string;
    success: string;
    warning: string;
    background: string;
    card: string;
    text: string;
    textSecondary: string;
  };
  dev: {
    enableLogging: boolean;
    enableDevTools: boolean;
  };
}

// Get environment variables from Expo Config
const env = Constants.expoConfig?.extra || {};

// Determine current environment
const isProduction = env.APP_ENV === 'production' || !__DEV__;
const isDevelopment = !isProduction;

// Environment-specific URLs with HTTPS enforcement
const getApiBaseUrl = (): string => {
  if (isDevelopment && env.DEV_API_BASE_URL) {
    return env.DEV_API_BASE_URL;
  }
  
  const prodUrl = env.API_BASE_URL || 'https://api.aiteddybear.com';
  
  // Enforce HTTPS in production
  if (isProduction && !prodUrl.startsWith('https://')) {
    console.error('🚨 SECURITY WARNING: Production API URL must use HTTPS!');
    throw new Error('Production API URL must use HTTPS');
  }
  
  return prodUrl;
};

const getWsBaseUrl = (): string => {
  if (isDevelopment && env.DEV_WS_BASE_URL) {
    return env.DEV_WS_BASE_URL;
  }
  
  const prodUrl = env.WS_BASE_URL || 'wss://api.aiteddybear.com';
  
  // Enforce WSS in production
  if (isProduction && !prodUrl.startsWith('wss://')) {
    console.error('🚨 SECURITY WARNING: Production WebSocket URL must use WSS!');
    throw new Error('Production WebSocket URL must use WSS');
  }
  
  return prodUrl;
};

// Production-ready configuration
export const config: AppConfig = {
  API_BASE_URL: getApiBaseUrl(),
  WS_BASE_URL: getWsBaseUrl(),
  
  // API Endpoints - نفس المسارات في FastAPI
  endpoints: {
    login: '/api/auth/login',
    logout: '/api/auth/logout',
    children: '/api/dashboard/children',
    interactions: '/api/dashboard/children/{childId}/interactions',
    safetyAlerts: '/api/dashboard/safety/alerts',
  },
  
  app: {
    name: 'AI Teddy Parent',
    version: env.APP_VERSION || '1.0.0',
    environment: isProduction ? 'production' : 'development',
    projectId: env.EXPO_PROJECT_ID || 'ai-teddy-bear-parent',
    maxInteractions: 10,
    refreshInterval: 30000, // 30 seconds
  },
  
  // Security Configuration
  security: {
    enableSSLPinning: env.ENABLE_SSL_PINNING === 'true' && isProduction,
    apiTimeout: parseInt(env.API_TIMEOUT || '15000', 10),
    enforceHTTPS: isProduction,
  },
  
  // Feature Flags
  features: {
    enablePushNotifications: env.ENABLE_PUSH_NOTIFICATIONS !== 'false',
    enableAnalytics: env.ENABLE_ANALYTICS !== 'false' && isProduction,
    enableCrashReporting: env.ENABLE_CRASH_REPORTING !== 'false' && isProduction,
  },
  
  // Colors
  colors: {
    primary: '#007AFF',
    secondary: '#FF3B30',
    success: '#34C759',
    warning: '#FF9500',
    background: '#f5f5f5',
    card: '#ffffff',
    text: '#333333',
    textSecondary: '#666666',
  },
  
  // Development settings
  dev: {
    enableLogging: env.ENABLE_LOGGING === 'true' || isDevelopment,
    enableDevTools: env.ENABLE_DEV_TOOLS === 'true' && isDevelopment,
  }
};

export default config;
