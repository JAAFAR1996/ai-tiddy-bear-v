/**
 * Secure Storage Service - خدمة التخزين الآمن
 * 
 * استخدام Expo SecureStore للتخزين الآمن للبيانات الحساسة
 * مثل tokens وبيانات المصادقة
 * 
 * @version 1.0.0
 * @since 2025-08-04
 */

import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';

export interface SecureStorageOptions {
  keychainService?: string;
  keychainAccessible?: any;
}

export class SecureStorageService {
  private static instance: SecureStorageService;
  private readonly options: SecureStorageOptions;

  private constructor(options: SecureStorageOptions = {}) {
    this.options = {
      keychainService: 'com.aiteddy.parent',
      ...options
    };
  }

  static getInstance(): SecureStorageService {
    if (!SecureStorageService.instance) {
      SecureStorageService.instance = new SecureStorageService();
    }
    return SecureStorageService.instance;
  }

  /**
   * حفظ قيمة بشكل آمن
   */
  async setSecureItem(key: string, value: string): Promise<void> {
    try {
      await SecureStore.setItemAsync(key, value, this.options);
      console.log(`✅ Securely stored: ${key}`);
    } catch (error) {
      console.error(`❌ Error storing secure item ${key}:`, error);
      throw new Error('Failed to store secure data');
    }
  }

  /**
   * قراءة قيمة آمنة
   */
  async getSecureItem(key: string): Promise<string | null> {
    try {
      const value = await SecureStore.getItemAsync(key, this.options);
      return value;
    } catch (error) {
      console.error(`❌ Error retrieving secure item ${key}:`, error);
      return null;
    }
  }

  /**
   * حذف قيمة آمنة
   */
  async deleteSecureItem(key: string): Promise<void> {
    try {
      await SecureStore.deleteItemAsync(key, this.options);
      console.log(`✅ Securely deleted: ${key}`);
    } catch (error) {
      console.error(`❌ Error deleting secure item ${key}:`, error);
      throw new Error('Failed to delete secure data');
    }
  }

  /**
   * التحقق من توفر SecureStore
   */
  async isAvailable(): Promise<boolean> {
    try {
      return await SecureStore.isAvailableAsync();
    } catch {
      return false;
    }
  }

  /**
   * ترحيل البيانات من AsyncStorage إلى SecureStore
   */
  async migrateFromAsyncStorage(keys: string[]): Promise<void> {
    console.log('🔄 Starting migration from AsyncStorage to SecureStore...');
    
    for (const key of keys) {
      try {
        // قراءة من AsyncStorage
        const value = await AsyncStorage.getItem(key);
        
        if (value) {
          // حفظ في SecureStore
          await this.setSecureItem(key, value);
          
          // حذف من AsyncStorage
          await AsyncStorage.removeItem(key);
          
          console.log(`✅ Migrated: ${key}`);
        }
      } catch (error) {
        console.error(`❌ Failed to migrate ${key}:`, error);
      }
    }
    
    console.log('✅ Migration completed');
  }

  /**
   * مسح جميع البيانات الآمنة (logout)
   */
  async clearAll(keys: string[]): Promise<void> {
    for (const key of keys) {
      try {
        await this.deleteSecureItem(key);
      } catch (error) {
        console.error(`Failed to clear ${key}:`, error);
      }
    }
  }
}

// Singleton instance
export const secureStorage = SecureStorageService.getInstance();

// Keys للبيانات الحساسة
export const SECURE_KEYS = {
  AUTH_TOKEN: 'authToken',
  REFRESH_TOKEN: 'refreshToken',
  USER_CREDENTIALS: 'userCredentials',
  BIOMETRIC_ENABLED: 'biometricEnabled',
  PIN_CODE: 'pinCode',
  DEVICE_ID: 'deviceId',
  ENCRYPTION_KEY: 'encryptionKey'
} as const;

// Helper functions للاستخدام السريع
export const SecureStorage = {
  setToken: async (token: string) => {
    return secureStorage.setSecureItem(SECURE_KEYS.AUTH_TOKEN, token);
  },
  
  getToken: async () => {
    return secureStorage.getSecureItem(SECURE_KEYS.AUTH_TOKEN);
  },
  
  removeToken: async () => {
    return secureStorage.deleteSecureItem(SECURE_KEYS.AUTH_TOKEN);
  },
  
  setRefreshToken: async (token: string) => {
    return secureStorage.setSecureItem(SECURE_KEYS.REFRESH_TOKEN, token);
  },
  
  getRefreshToken: async () => {
    return secureStorage.getSecureItem(SECURE_KEYS.REFRESH_TOKEN);
  },
  
  clear: async () => {
    return secureStorage.clearAll(Object.values(SECURE_KEYS));
  },
  
  migrate: async () => {
    return secureStorage.migrateFromAsyncStorage(Object.values(SECURE_KEYS));
  }
};

export default SecureStorage;