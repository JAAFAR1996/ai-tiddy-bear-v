/**
 * SecureStorage Service Test
 * 
 * Tests the secure token storage functionality and migration
 */

import { SecureStorage } from '../src/services/SecureStorageService';
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Mock expo-secure-store with proper typing
jest.mock('expo-secure-store');
const mockSecureStore = SecureStore as jest.Mocked<typeof SecureStore>;

// Mock AsyncStorage for migration test with proper typing
jest.mock('@react-native-async-storage/async-storage');
const mockAsyncStorage = AsyncStorage as jest.Mocked<typeof AsyncStorage>;

describe('SecureStorage Service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should store token securely', async () => {
    const testToken = 'test-jwt-token-123';
    
    await SecureStorage.setToken(testToken);
    
    // Verify that SecureStore was called with proper typing
    expect(mockSecureStore.setItemAsync).toHaveBeenCalledWith('auth_token', testToken, expect.any(Object));
  });

  test('should retrieve token from secure storage', async () => {
    const testToken = 'test-jwt-token-123';
    mockSecureStore.getItemAsync.mockResolvedValue(testToken);
    
    const result = await SecureStorage.getToken();
    
    expect(result).toBe(testToken);
    expect(mockSecureStore.getItemAsync).toHaveBeenCalledWith('auth_token');
  });

  test('should remove token from secure storage', async () => {
    await SecureStorage.removeToken();
    
    expect(mockSecureStore.deleteItemAsync).toHaveBeenCalledWith('auth_token');
  });

  test('should migrate tokens from AsyncStorage', async () => {
    const testToken = 'migrated-token-123';
    
    // Mock AsyncStorage having old token
    mockAsyncStorage.getItem.mockResolvedValue(testToken);
    // Mock SecureStore not having token yet
    mockSecureStore.getItemAsync.mockResolvedValue(null);
    
    await SecureStorage.migrate();
    
    // Should have migrated the token
    expect(mockSecureStore.setItemAsync).toHaveBeenCalledWith('auth_token', testToken, expect.any(Object));
    // Should have removed from AsyncStorage
    expect(mockAsyncStorage.removeItem).toHaveBeenCalledWith('authToken');
  });

  test('should handle migration when no old token exists', async () => {
    // Mock no old token
    mockAsyncStorage.getItem.mockResolvedValue(null);
    
    await SecureStorage.migrate();
    
    // Should not attempt to migrate
    expect(mockSecureStore.setItemAsync).not.toHaveBeenCalled();
  });
});