/**
 * Notification Settings Screen
 * 
 * Features:
 * - Push notification preferences
 * - Permission management
 * - Notification categories
 * - Test notifications
 * - Troubleshooting
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Switch,
  TouchableOpacity,
  Alert,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { PushNotificationService } from '../services/PushNotificationService';
import { config } from '../config';

interface NotificationSettings {
  pushEnabled: boolean;
  safetyAlerts: boolean;
  childUpdates: boolean;
  systemNotifications: boolean;
  soundEnabled: boolean;
  vibrationEnabled: boolean;
}

interface NotificationStatus {
  permissions: any;
  hasToken: boolean;
  token: string | null;
  initialized: boolean;
  enabledInConfig: boolean;
}

export default function NotificationSettingsScreen() {
  const [settings, setSettings] = useState<NotificationSettings>({
    pushEnabled: true,
    safetyAlerts: true,
    childUpdates: true,
    systemNotifications: false,
    soundEnabled: true,
    vibrationEnabled: true,
  });

  const [status, setStatus] = useState<NotificationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadNotificationStatus();
  }, []);

  const loadNotificationStatus = async () => {
    try {
      setLoading(true);
      const pushService = PushNotificationService.getInstance();
      const notificationStatus = await pushService.getNotificationSettings();
      setStatus(notificationStatus);
    } catch (error) {
      console.error('❌ Error loading notification status:', error);
      Alert.alert('خطأ', 'فشل في تحميل إعدادات الإشعارات');
    } finally {
      setLoading(false);
    }
  };

  const refreshStatus = async () => {
    setRefreshing(true);
    await loadNotificationStatus();
    setRefreshing(false);
  };

  const handleToggle = (key: keyof NotificationSettings) => {
    setSettings(prev => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const requestPermissions = async () => {
    try {
      const pushService = PushNotificationService.getInstance();
      const result = await pushService.requestPermissions();
      
      if (result.granted) {
        Alert.alert('تم!', 'تم منح إذن الإشعارات بنجاح');
        await refreshStatus();
      } else {
        Alert.alert(
          'إذن مطلوب',
          'يرجى السماح بالإشعارات في إعدادات الجهاز لتلقي تنبيهات الأمان المهمة',
          [
            { text: 'إلغاء', style: 'cancel' },
            { text: 'فتح الإعدادات', onPress: () => {
              // Open device settings
            }},
          ]
        );
      }
    } catch (error) {
      console.error('❌ Error requesting permissions:', error);
      Alert.alert('خطأ', 'فشل في طلب إذن الإشعارات');
    }
  };

  const sendTestNotification = async () => {
    try {
      const pushService = PushNotificationService.getInstance();
      await pushService.sendLocalNotification({
        type: 'system_notification',
        title: '🧸 AI Teddy Bear',
        body: 'هذا إشعار تجريبي للتأكد من عمل الإشعارات',
        priority: 'normal',
      });
      
      Alert.alert('تم!', 'تم إرسال الإشعار التجريبي');
    } catch (error) {
      console.error('❌ Error sending test notification:', error);
      Alert.alert('خطأ', 'فشل في إرسال الإشعار التجريبي');
    }
  };

  const refreshPushToken = async () => {
    try {
      const pushService = PushNotificationService.getInstance();
      const newToken = await pushService.refreshPushToken();
      
      if (newToken) {
        Alert.alert('تم!', 'تم تحديث رمز الإشعارات');
        await refreshStatus();
      } else {
        Alert.alert('خطأ', 'فشل في تحديث رمز الإشعارات');
      }
    } catch (error) {
      console.error('❌ Error refreshing push token:', error);
      Alert.alert('خطأ', 'فشل في تحديث رمز الإشعارات');
    }
  };

  const renderStatusCard = () => {
    if (!status) return null;

    const getStatusColor = () => {
      if (!status.enabledInConfig) return '#FF3B30';
      if (!status.permissions?.granted) return '#FF9500';
      if (!status.hasToken) return '#FF9500';
      return '#34C759';
    };

    const getStatusText = () => {
      if (!status.enabledInConfig) return 'معطل في الإعدادات';
      if (!status.permissions?.granted) return 'إذن مطلوب';
      if (!status.hasToken) return 'رمز غير متوفر';
      return 'يعمل بشكل طبيعي';
    };

    return (
      <View style={styles.statusCard}>
        <Text style={styles.statusTitle}>حالة الإشعارات</Text>
        <View style={styles.statusRow}>
          <View style={[styles.statusIndicator, { backgroundColor: getStatusColor() }]} />
          <Text style={styles.statusText}>{getStatusText()}</Text>
        </View>
        
        <View style={styles.statusDetails}>
          <Text style={styles.statusDetail}>الإذن: {status.permissions?.granted ? '✅ ممنوح' : '❌ غير ممنوح'}</Text>
          <Text style={styles.statusDetail}>الرمز: {status.hasToken ? '✅ متوفر' : '❌ غير متوفر'}</Text>
          <Text style={styles.statusDetail}>التهيئة: {status.initialized ? '✅ تم' : '❌ لم يتم'}</Text>
        </View>
      </View>
    );
  };

  const renderSettingRow = (
    key: keyof NotificationSettings,
    title: string,
    description: string,
    enabled: boolean = true
  ) => (
    <View style={[styles.settingRow, !enabled && styles.settingRowDisabled]}>
      <View style={styles.settingInfo}>
        <Text style={[styles.settingTitle, !enabled && styles.settingTitleDisabled]}>
          {title}
        </Text>
        <Text style={[styles.settingDescription, !enabled && styles.settingDescriptionDisabled]}>
          {description}
        </Text>
      </View>
      <Switch
        value={settings[key] && enabled}
        onValueChange={() => handleToggle(key)}
        disabled={!enabled}
        trackColor={{ false: '#767577', true: '#007AFF' }}
        thumbColor={settings[key] ? '#007AFF' : '#f4f3f4'}
      />
    </View>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>جاري تحميل إعدادات الإشعارات...</Text>
      </View>
    );
  }

  const isEnabled = status?.enabledInConfig && status?.permissions?.granted;

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>إعدادات الإشعارات</Text>
        <Text style={styles.headerSubtitle}>
          إدارة تنبيهات الأمان وإشعارات التطبيق
        </Text>
      </View>

      {renderStatusCard()}

      {!config.features.enablePushNotifications && (
        <View style={styles.disabledCard}>
          <Text style={styles.disabledTitle}>⚠️ الإشعارات معطلة</Text>
          <Text style={styles.disabledText}>
            الإشعارات معطلة في تكوين التطبيق. يرجى التواصل مع المطور لتفعيلها.
          </Text>
        </View>
      )}

      {status && !status.permissions?.granted && (
        <TouchableOpacity style={styles.actionButton} onPress={requestPermissions}>
          <Text style={styles.actionButtonText}>🔔 طلب إذن الإشعارات</Text>
        </TouchableOpacity>
      )}

      <View style={styles.settingsSection}>
        <Text style={styles.sectionTitle}>أنواع الإشعارات</Text>
        
        {renderSettingRow(
          'safetyAlerts',
          '🚨 تنبيهات الأمان',
          'إشعارات فورية عند حدوث مشاكل أمان',
          isEnabled
        )}
        
        {renderSettingRow(
          'childUpdates',
          '👶 تحديثات الأطفال',
          'إشعارات عن أنشطة الأطفال وحالتهم',
          isEnabled
        )}
        
        {renderSettingRow(
          'systemNotifications',
          '🔔 إشعارات النظام',
          'تحديثات التطبيق والصيانة',
          isEnabled
        )}
      </View>

      <View style={styles.settingsSection}>
        <Text style={styles.sectionTitle}>إعدادات الصوت</Text>
        
        {renderSettingRow(
          'soundEnabled',
          '🔊 الصوت',
          'تشغيل الأصوات مع الإشعارات',
          isEnabled
        )}
        
        {renderSettingRow(
          'vibrationEnabled',
          '📳 الاهتزاز',
          'اهتزاز الجهاز مع الإشعارات',
          isEnabled
        )}
      </View>

      <View style={styles.actionsSection}>
        <TouchableOpacity
          style={[styles.actionButton, styles.testButton]}
          onPress={sendTestNotification}
          disabled={!isEnabled}
        >
          <Text style={styles.actionButtonText}>🧪 إرسال إشعار تجريبي</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionButton, styles.refreshButton]}
          onPress={refreshPushToken}
          disabled={!isEnabled}
        >
          <Text style={styles.actionButtonText}>🔄 تحديث رمز الإشعارات</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionButton, styles.refreshButton]}
          onPress={refreshStatus}
        >
          <Text style={styles.actionButtonText}>
            {refreshing ? '⏳ جاري التحديث...' : '🔄 تحديث الحالة'}
          </Text>
        </TouchableOpacity>
      </View>

      {status?.token && (
        <View style={styles.debugSection}>
          <Text style={styles.debugTitle}>معلومات تقنية</Text>
          <Text style={styles.debugText}>رمز الإشعارات: {status.token}</Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#666',
  },
  header: {
    padding: 20,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    textAlign: 'right',
  },
  headerSubtitle: {
    fontSize: 16,
    color: '#666',
    marginTop: 5,
    textAlign: 'right',
  },
  statusCard: {
    margin: 20,
    padding: 20,
    backgroundColor: '#fff',
    borderRadius: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  statusTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 10,
    textAlign: 'right',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    marginBottom: 10,
  },
  statusIndicator: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginLeft: 10,
  },
  statusText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  statusDetails: {
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#eee',
  },
  statusDetail: {
    fontSize: 14,
    color: '#666',
    marginBottom: 5,
    textAlign: 'right',
  },
  disabledCard: {
    margin: 20,
    padding: 20,
    backgroundColor: '#FFF3CD',
    borderRadius: 10,
    borderLeftWidth: 4,
    borderLeftColor: '#FF9500',
  },
  disabledTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#856404',
    marginBottom: 5,
    textAlign: 'right',
  },
  disabledText: {
    fontSize: 14,
    color: '#856404',
    textAlign: 'right',
  },
  settingsSection: {
    margin: 20,
    backgroundColor: '#fff',
    borderRadius: 10,
    overflow: 'hidden',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
    padding: 20,
    paddingBottom: 10,
    textAlign: 'right',
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 20,
    borderTopWidth: 1,
    borderTopColor: '#eee',
  },
  settingRowDisabled: {
    opacity: 0.5,
  },
  settingInfo: {
    flex: 1,
    marginRight: 15,
  },
  settingTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    textAlign: 'right',
  },
  settingTitleDisabled: {
    color: '#999',
  },
  settingDescription: {
    fontSize: 14,
    color: '#666',
    marginTop: 2,
    textAlign: 'right',
  },
  settingDescriptionDisabled: {
    color: '#999',
  },
  actionsSection: {
    margin: 20,
  },
  actionButton: {
    backgroundColor: '#007AFF',
    padding: 15,
    borderRadius: 10,
    marginBottom: 10,
    alignItems: 'center',
  },
  testButton: {
    backgroundColor: '#34C759',
  },
  refreshButton: {
    backgroundColor: '#FF9500',
  },
  actionButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  debugSection: {
    margin: 20,
    padding: 20,
    backgroundColor: '#f8f8f8',
    borderRadius: 10,
  },
  debugTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#666',
    marginBottom: 10,
    textAlign: 'right',
  },
  debugText: {
    fontSize: 12,
    fontFamily: 'monospace',
    color: '#666',
    textAlign: 'right',
  },
});