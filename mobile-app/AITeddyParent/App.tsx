import React, { useState, useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { View, ActivityIndicator, StyleSheet } from 'react-native';

import LoginScreen from './src/screens/LoginScreen';
import DashboardScreen from './src/screens/DashboardScreen';
import { SecureStorage } from './src/services/SecureStorageService';
import { PushNotificationService } from './src/services/PushNotificationService';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      // Migrate from AsyncStorage to SecureStore on first run
      await SecureStorage.migrate();
      
      // Check for token in secure storage
      const token = await SecureStorage.getToken();
      setIsAuthenticated(!!token);
      
      // Initialize push notifications if user is authenticated
      if (token) {
        await initializePushNotifications();
      }
    } catch (error) {
      console.error('Error checking auth status:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const initializePushNotifications = async () => {
    try {
      console.log('🚀 Initializing push notifications...');
      const pushService = PushNotificationService.getInstance();
      await pushService.initialize();
    } catch (error) {
      console.error('❌ Failed to initialize push notifications:', error);
      // Don't throw - app should work without push notifications
    }
  };

  const handleLoginSuccess = async () => {
    setIsAuthenticated(true);
    // Initialize push notifications after login
    await initializePushNotifications();
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
  };

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <StatusBar style="auto" />
      {isAuthenticated ? (
        <DashboardScreen onLogout={handleLogout} />
      ) : (
        <LoginScreen onLoginSuccess={handleLoginSuccess} />
      )}
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
  },
});
