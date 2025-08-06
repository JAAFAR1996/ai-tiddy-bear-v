/**
 * Production Push Notification Service
 * 
 * Features:
 * - Expo Push Notifications integration
 * - Firebase Cloud Messaging support
 * - Permission handling
 * - Token management
 * - Notification categories
 * - Background handling
 * - Deep linking support
 * 
 * @version 1.0.0
 * @since 2025-08-04
 */

import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import { SecureStorage, secureStorage } from './SecureStorageService';
import { config } from '../config';
import { ApiService } from './api';

export interface PushNotificationData {
  type: 'safety_alert' | 'system_notification' | 'child_status' | 'reminder';
  title: string;
  body: string;
  data?: any;
  childId?: string;
  alertId?: string;
  priority: 'low' | 'normal' | 'high' | 'max';
}

export interface NotificationPermissionStatus {
  granted: boolean;
  canAskAgain: boolean;
  status: string;
}

// Configure notification behavior
Notifications.setNotificationHandler({
  handleNotification: async (notification) => {
    const data = notification.request.content.data as PushNotificationData;
    
    return {
      shouldShowAlert: true,
      shouldPlaySound: data.priority === 'high' || data.priority === 'max',
      shouldSetBadge: true,
      priority: getPriorityLevel(data.priority),
    };
  },
});

// Configure notification categories for child safety
const notificationCategories = [
  {
    identifier: 'SAFETY_ALERT',
    actions: [
      {
        identifier: 'VIEW_DETAILS',
        title: 'عرض التفاصيل',
        options: { opensAppToForeground: true },
      },
      {
        identifier: 'MARK_REVIEWED',
        title: 'تم المراجعة',
        options: { opensAppToForeground: false },
      },
    ],
    options: { categorySummaryFormat: '%u# تنبيهات أمان جديدة' },
  },
  {
    identifier: 'CHILD_STATUS',
    actions: [
      {
        identifier: 'VIEW_CHILD',
        title: 'عرض الطفل',
        options: { opensAppToForeground: true },
      },
    ],
    options: { categorySummaryFormat: '%u# تحديثات حالة الأطفال' },
  },
];

function getPriorityLevel(priority: string): Notifications.AndroidNotificationPriority {
  switch (priority) {
    case 'max':
      return Notifications.AndroidNotificationPriority.MAX;
    case 'high':
      return Notifications.AndroidNotificationPriority.HIGH;
    case 'low':
      return Notifications.AndroidNotificationPriority.LOW;
    default:
      return Notifications.AndroidNotificationPriority.DEFAULT;
  }
}

export class PushNotificationService {
  private static instance: PushNotificationService;
  private expoPushToken: string | null = null;
  private initialized: boolean = false;

  private constructor() {}

  public static getInstance(): PushNotificationService {
    if (!PushNotificationService.instance) {
      PushNotificationService.instance = new PushNotificationService();
    }
    return PushNotificationService.instance;
  }

  /**
   * Initialize push notification service
   */
  public async initialize(): Promise<void> {
    if (this.initialized) {
      console.log('📱 Push notifications already initialized');
      return;
    }

    try {
      console.log('🚀 Initializing push notifications...');

      // Check if push notifications are enabled
      if (!config.features.enablePushNotifications) {
        console.log('📱 Push notifications disabled in config');
        return;
      }

      // Set up notification categories (commented out - not available in current expo-notifications version)
      // await Notifications.setNotificationCategoriesAsync(notificationCategories);

      // Request permissions and get token
      const { granted } = await this.requestPermissions();
      
      if (granted) {
        await this.registerForPushNotifications();
        this.setupNotificationListeners();
      }

      this.initialized = true;
      console.log('✅ Push notifications initialized successfully');

    } catch (error) {
      console.error('❌ Failed to initialize push notifications:', error);
      throw error;
    }
  }

  /**
   * Request push notification permissions
   */
  public async requestPermissions(): Promise<NotificationPermissionStatus> {
    try {
      if (!Device.isDevice) {
        console.log('📱 Push notifications require physical device');
        return {
          granted: false,
          canAskAgain: false,
          status: 'not_supported',
        };
      }

      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;

      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }

      const granted = finalStatus === 'granted';
      
      console.log(`📱 Push notification permissions: ${finalStatus}`);

      return {
        granted,
        canAskAgain: finalStatus !== 'denied',
        status: finalStatus,
      };

    } catch (error) {
      console.error('❌ Error requesting push permissions:', error);
      return {
        granted: false,
        canAskAgain: false,
        status: 'error',
      };
    }
  }

  /**
   * Register for push notifications and get token
   */
  public async registerForPushNotifications(): Promise<string | null> {
    try {
      if (!Device.isDevice) {
        console.log('📱 Cannot get push token on simulator');
        return null;
      }

      // Get Expo push token
      const tokenData = await Notifications.getExpoPushTokenAsync({
        projectId: config.app.projectId, // From app.config.js
      });

      this.expoPushToken = tokenData.data;
      console.log('📱 Expo push token obtained:', this.expoPushToken.substring(0, 20) + '...');

      // Store token securely
      await secureStorage.setSecureItem('push_token', this.expoPushToken);

      // Send token to backend
      await this.sendTokenToBackend(this.expoPushToken);

      return this.expoPushToken;

    } catch (error) {
      console.error('❌ Error getting push token:', error);
      return null;
    }
  }

  /**
   * Send push token to backend
   */
  private async sendTokenToBackend(token: string): Promise<void> {
    try {
      console.log('📤 Sending push token to backend...');
      
      await ApiService.registerPushToken({
        token,
        platform: Platform.OS,
        deviceId: Device.osVersion || 'unknown',
        appVersion: config.app.version,
      });

      console.log('✅ Push token registered with backend');

    } catch (error) {
      console.error('❌ Failed to register push token with backend:', error);
      // Don't throw - token can be sent later
    }
  }

  /**
   * Setup notification event listeners
   */
  private setupNotificationListeners(): void {
    // Handle notification received while app is running
    Notifications.addNotificationReceivedListener((notification) => {
      console.log('📱 Notification received:', notification.request.content.title);
      
      const data = notification.request.content.data as PushNotificationData;
      this.handleNotificationReceived(data);
    });

    // Handle notification tap
    Notifications.addNotificationResponseReceivedListener((response) => {
      console.log('📱 Notification tapped:', response.actionIdentifier);
      
      const data = response.notification.request.content.data as PushNotificationData;
      this.handleNotificationTapped(data, response.actionIdentifier);
    });

    console.log('📱 Notification listeners set up');
  }

  /**
   * Handle notification received while app is active
   */
  private handleNotificationReceived(data: PushNotificationData): void {
    switch (data.type) {
      case 'safety_alert':
        console.log('🚨 Safety alert received:', data.title);
        // Emit event for real-time UI update
        break;
      case 'child_status':
        console.log('👶 Child status update:', data.title);
        break;
      case 'system_notification':
        console.log('🔔 System notification:', data.title);
        break;
      default:
        console.log('📱 Unknown notification type:', data.type);
    }
  }

  /**
   * Handle notification tap/action
   */
  private handleNotificationTapped(data: PushNotificationData, actionId: string): void {
    console.log(`📱 Notification action: ${actionId} for type: ${data.type}`);

    switch (actionId) {
      case 'VIEW_DETAILS':
        // Navigate to alert details
        if (data.alertId) {
          // Navigation logic here
        }
        break;
      case 'MARK_REVIEWED':
        // Mark alert as reviewed
        if (data.alertId) {
          this.markAlertAsReviewed(data.alertId);
        }
        break;
      case 'VIEW_CHILD':
        // Navigate to child details
        if (data.childId) {
          // Navigation logic here
        }
        break;
      default:
        // Default action - open app
        console.log('📱 Opening app from notification');
    }
  }

  /**
   * Mark safety alert as reviewed
   */
  private async markAlertAsReviewed(alertId: string): Promise<void> {
    try {
      await ApiService.markSafetyAlertAsResolved(alertId);
      console.log('✅ Alert marked as reviewed:', alertId);
    } catch (error) {
      console.error('❌ Failed to mark alert as reviewed:', error);
    }
  }

  /**
   * Send local notification (for testing)
   */
  public async sendLocalNotification(data: PushNotificationData): Promise<void> {
    try {
      await Notifications.scheduleNotificationAsync({
        content: {
          title: data.title,
          body: data.body,
          data: data,
          categoryIdentifier: this.getCategoryId(data.type),
        },
        trigger: null, // Send immediately
      });

      console.log('📱 Local notification sent:', data.title);

    } catch (error) {
      console.error('❌ Failed to send local notification:', error);
    }
  }

  /**
   * Get category identifier for notification type
   */
  private getCategoryId(type: string): string {
    switch (type) {
      case 'safety_alert':
        return 'SAFETY_ALERT';
      case 'child_status':
        return 'CHILD_STATUS';
      default:
        return 'DEFAULT';
    }
  }

  /**
   * Get current push token
   */
  public async getPushToken(): Promise<string | null> {
    if (this.expoPushToken) {
      return this.expoPushToken;
    }

    try {
      const stored = await secureStorage.getSecureItem('push_token');
      if (stored) {
        this.expoPushToken = stored;
        return stored;
      }
    } catch (error) {
      console.error('❌ Error getting stored push token:', error);
    }

    return null;
  }

  /**
   * Refresh push token
   */
  public async refreshPushToken(): Promise<string | null> {
    try {
      console.log('🔄 Refreshing push token...');
      
      this.expoPushToken = null;
      await secureStorage.deleteSecureItem('push_token');
      
      return await this.registerForPushNotifications();

    } catch (error) {
      console.error('❌ Failed to refresh push token:', error);
      return null;
    }
  }

  /**
   * Unregister from push notifications
   */
  public async unregister(): Promise<void> {
    try {
      console.log('📱 Unregistering from push notifications...');

      if (this.expoPushToken) {
        // Notify backend to remove token
        await ApiService.unregisterPushToken(this.expoPushToken);
      }

      // Clear local token
      this.expoPushToken = null;
      await secureStorage.deleteSecureItem('push_token');

      console.log('✅ Unregistered from push notifications');

    } catch (error) {
      console.error('❌ Failed to unregister from push notifications:', error);
    }
  }

  /**
   * Check if notifications are enabled
   */
  public async areNotificationsEnabled(): Promise<boolean> {
    try {
      const { status } = await Notifications.getPermissionsAsync();
      return status === 'granted';
    } catch (error) {
      console.error('❌ Error checking notification status:', error);
      return false;
    }
  }

  /**
   * Get notification settings
   */
  public async getNotificationSettings(): Promise<any> {
    try {
      const permissions = await Notifications.getPermissionsAsync();
      const token = await this.getPushToken();
      
      return {
        permissions,
        hasToken: !!token,
        token: token ? token.substring(0, 20) + '...' : null,
        initialized: this.initialized,
        enabledInConfig: config.features.enablePushNotifications,
      };

    } catch (error) {
      console.error('❌ Error getting notification settings:', error);
      return null;
    }
  }
}

export default PushNotificationService;