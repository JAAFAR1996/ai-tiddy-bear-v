/**
 * Notification Service - خدمة الإشعارات والتنبيهات
 * 
 * Features:
 * - Push notifications for safety alerts
 * - Local notifications for offline alerts
 * - Priority-based notification handling
 * - Sound and vibration patterns
 * - Notification history and management
 * - COPPA-compliant notification content
 * 
 * @version 1.0.0
 * @since 2025-08-04
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { Alert as ReactNativeAlert, Vibration } from 'react-native';
import { EventEmitter } from 'events';

// سيتم استبدال هذا بمكتبة push notifications حقيقية
// import PushNotification from 'react-native-push-notification';

export interface NotificationData {
  id: string;
  title: string;
  body: string;
  data?: any;
  priority: 'low' | 'normal' | 'high' | 'critical';
  sound?: string;
  vibration?: number[];
  badge?: number;
  category?: string;
}

export interface NotificationConfig {
  enabled: boolean;
  sound: boolean;
  vibration: boolean;
  critical_alerts: boolean;
  quiet_hours: {
    enabled: boolean;
    start: string; // "22:00"
    end: string;   // "07:00"
  };
  categories: {
    safety: boolean;
    updates: boolean;
    reports: boolean;
  };
}

export interface Alert {
  id: string;
  child_id: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  requires_immediate_action: boolean;
}

export class NotificationService extends EventEmitter {
  private static instance: NotificationService;
  private config: NotificationConfig = {
    enabled: true,
    sound: true,
    vibration: true,
    critical_alerts: true,
    quiet_hours: {
      enabled: false,
      start: "22:00",
      end: "07:00"
    },
    categories: {
      safety: true,
      updates: true,
      reports: true
    }
  };
  private notificationHistory: NotificationData[] = [];
  private isInitialized: boolean = false;

  private constructor() {
    super();
  }

  public static getInstance(): NotificationService {
    if (!NotificationService.instance) {
      NotificationService.instance = new NotificationService();
    }
    return NotificationService.instance;
  }

  /**
   * تهيئة خدمة الإشعارات
   */
  public async initialize(): Promise<void> {
    try {
      console.log('🔔 Initializing Notification Service...');

      // تحميل الإعدادات المحفوظة
      await this.loadConfig();

      // طلب صلاحيات الإشعارات (سيتم تنفيذه مع مكتبة حقيقية)
      await this.requestPermissions();

      // تكوين الفئات والأصوات
      this.configurePushNotifications();

      this.isInitialized = true;
      console.log('✅ Notification Service initialized');

    } catch (error) {
      console.error('❌ Failed to initialize notifications:', error);
      throw error;
    }
  }

  /**
   * إرسال تنبيه أمان
   */
  public async sendAlertNotification(alert: Alert): Promise<void> {
    if (!this.isInitialized || !this.config.enabled) {
      console.log('🔕 Notifications disabled or not initialized');
      return;
    }

    try {
      console.log('🚨 Sending safety alert notification:', alert.id);

      const notification = this.createAlertNotification(alert);
      
      // تحقق من الساعات الهادئة (إلا للحالات الحرجة)
      if (this.isQuietTime() && alert.severity !== 'critical') {
        console.log('🌙 Quiet hours - scheduling notification');
        await this.scheduleNotification(notification);
        return;
      }

      // إرسال فوري
      await this.sendNotification(notification);

      // اهتزاز للتنبيهات المهمة
      if (alert.severity === 'high' || alert.severity === 'critical') {
        this.triggerVibration(alert.severity);
      }

      // تشغيل صوت التنبيه
      await this.playAlertSound(alert.severity);

      // حفظ في التاريخ
      this.addToHistory(notification);

    } catch (error) {
      console.error('❌ Error sending alert notification:', error);
    }
  }

  /**
   * إرسال تنبيه حرج (طارئ)
   */
  public async sendCriticalNotification(alert: Alert): Promise<void> {
    try {
      console.log('🚨 CRITICAL ALERT NOTIFICATION:', alert.id);

      // إشعار فوري مع صوت وحد
      const notification: NotificationData = {
        id: `critical_${alert.id}`,
        title: '⚠️ تنبيه أمان حرج',
        body: `تحتاج ${alert.type} لتدخل فوري`,
        priority: 'critical',
        sound: 'critical_alert.mp3',
        vibration: [0, 1000, 500, 1000, 500, 1000],
        category: 'CRITICAL_SAFETY'
      };

      // إرسال حتى في الساعات الهادئة
      await this.sendNotification(notification);

      // اهتزاز قوي
      this.triggerCriticalVibration();

      // إشعار نظام محلي (Alert Dialog)
      this.showCriticalAlert(alert);

      // حفظ في سجل الطوارئ
      await this.logCriticalNotification(alert);

    } catch (error) {
      console.error('❌ Error sending critical notification:', error);
    }
  }

  /**
   * إرسال إشعار تقرير
   */
  public async sendReportNotification(reportType: string, childName: string): Promise<void> {
    if (!this.config.categories.reports) return;

    try {
      const notification: NotificationData = {
        id: `report_${Date.now()}`,
        title: '📊 تقرير جديد متاح',
        body: `تقرير ${reportType} لـ ${childName} جاهز للمراجعة`,
        priority: 'normal',
        sound: 'notification.mp3',
        category: 'REPORT'
      };

      await this.sendNotification(notification);
      this.addToHistory(notification);

    } catch (error) {
      console.error('❌ Error sending report notification:', error);
    }
  }

  /**
   * إرسال إشعار تحديث
   */
  public async sendUpdateNotification(title: string, message: string): Promise<void> {
    if (!this.config.categories.updates) return;

    try {
      const notification: NotificationData = {
        id: `update_${Date.now()}`,
        title: title,
        body: message,
        priority: 'low',
        sound: 'update.mp3',
        category: 'UPDATE'
      };

      await this.sendNotification(notification);
      this.addToHistory(notification);

    } catch (error) {
      console.error('❌ Error sending update notification:', error);
    }
  }

  /**
   * إنشاء إشعار من التنبيه
   */
  private createAlertNotification(alert: Alert): NotificationData {
    const priorityEmojis = {
      low: '🟡',
      medium: '🟠', 
      high: '🔴',
      critical: '🚨'
    };

    const typeMessages = {
      forbidden_content: 'محتوى غير مناسب',
      self_harm: 'مؤشرات إيذاء النفس',
      excessive_usage: 'استخدام مفرط',
      inappropriate_interaction: 'تفاعل غير مناسب',
      emergency: 'حالة طارئة'
    };

    return {
      id: `alert_${alert.id}`,
      title: `${priorityEmojis[alert.severity]} تنبيه أمان`,
      body: typeMessages[alert.type as keyof typeof typeMessages] || alert.message,
      priority: alert.severity === 'medium' ? 'normal' : alert.severity,
      sound: this.getAlertSound(alert.severity),
      vibration: this.getVibrationPattern(alert.severity) || undefined,
      category: 'SAFETY_ALERT',
      data: {
        alert_id: alert.id,
        child_id: alert.child_id,
        type: alert.type,
        severity: alert.severity
      }
    };
  }

  /**
   * إرسال الإشعار الفعلي
   */
  private async sendNotification(notification: NotificationData): Promise<void> {
    try {
      // في البيئة الحالية سنستخدم console.log
      // في التطبيق الحقيقي سيتم استبدال هذا بـ PushNotification
      
      console.log('📱 Sending Notification:', {
        title: notification.title,
        body: notification.body,
        priority: notification.priority
      });

      // محاكاة إرسال push notification
      // PushNotification.localNotification({
      //   id: notification.id,
      //   title: notification.title,
      //   message: notification.body,
      //   priority: notification.priority,
      //   soundName: notification.sound,
      //   vibrate: notification.vibration,
      //   userInfo: notification.data
      // });

      this.emit('notification_sent', notification);

    } catch (error) {
      console.error('❌ Error sending push notification:', error);
      throw error;
    }
  }

  /**
   * جدولة إشعار للوقت المناسب
   */
  private async scheduleNotification(notification: NotificationData): Promise<void> {
    try {
      // حساب وقت انتهاء الساعات الهادئة
      const scheduleTime = this.calculateScheduleTime();
      
      console.log('⏰ Scheduling notification for:', scheduleTime);

      // حفظ الإشعار المجدول محلياً
      const scheduledNotifications = await this.getScheduledNotifications();
      scheduledNotifications.push({
        notification,
        scheduleTime: scheduleTime.toISOString()
      });

      await AsyncStorage.setItem('scheduled_notifications', JSON.stringify(scheduledNotifications));

      this.emit('notification_scheduled', notification);

    } catch (error) {
      console.error('❌ Error scheduling notification:', error);
    }
  }

  /**
   * إظهار تنبيه حرج محلي
   */
  private showCriticalAlert(alert: Alert): void {
    ReactNativeAlert.alert(
      '🚨 تنبيه أمان حرج',
      `تم اكتشاف ${alert.type} ويحتاج لتدخل فوري.\n\nالرسالة: ${alert.message}`,
      [
        {
          text: 'مراجعة فوراً',
          style: 'default',
          onPress: () => {
            this.emit('critical_alert_action', { action: 'review', alert });
          }
        },
        {
          text: 'اتصال طوارئ',
          style: 'destructive',
          onPress: () => {
            this.emit('critical_alert_action', { action: 'emergency_call', alert });
          }
        }
      ],
      { cancelable: false }
    );
  }

  /**
   * تشغيل اهتزاز حسب الخطورة
   */
  private triggerVibration(severity: string): void {
    if (!this.config.vibration) return;

    const pattern = this.getVibrationPattern(severity);
    if (pattern) {
      Vibration.vibrate(pattern);
    }
  }

  /**
   * تشغيل اهتزاز حرج
   */
  private triggerCriticalVibration(): void {
    if (!this.config.vibration) return;

    // اهتزاز قوي ومتكرر للحالات الحرجة
    const criticalPattern = [0, 1000, 500, 1000, 500, 1000, 500, 1000];
    Vibration.vibrate(criticalPattern);
  }

  /**
   * الحصول على نمط الاهتزاز
   */
  private getVibrationPattern(severity: string): number[] | null {
    const patterns = {
      low: [0, 200],
      medium: [0, 400, 200, 400],
      high: [0, 600, 300, 600],
      critical: [0, 1000, 500, 1000, 500, 1000]
    };

    return patterns[severity as keyof typeof patterns] || null;
  }

  /**
   * الحصول على صوت التنبيه
   */
  private getAlertSound(severity: string): string {
    const sounds = {
      low: 'notification.mp3',
      medium: 'alert.mp3',
      high: 'warning.mp3',
      critical: 'critical_alert.mp3'
    };

    return sounds[severity as keyof typeof sounds] || 'notification.mp3';
  }

  /**
   * تشغيل صوت التنبيه
   */
  private async playAlertSound(severity: string): Promise<void> {
    if (!this.config.sound) return;

    try {
      const soundFile = this.getAlertSound(severity);
      console.log('🔊 Playing alert sound:', soundFile);
      
      // في التطبيق الحقيقي سيتم تشغيل الصوت
      // await SoundPlayer.playSoundFile(soundFile, 'mp3');
      
    } catch (error) {
      console.error('❌ Error playing sound:', error);
    }
  }

  /**
   * التحقق من الساعات الهادئة
   */
  private isQuietTime(): boolean {
    if (!this.config.quiet_hours.enabled) return false;

    const now = new Date();
    const currentTime = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    
    const startTime = this.config.quiet_hours.start;
    const endTime = this.config.quiet_hours.end;

    // التعامل مع الساعات التي تعبر منتصف الليل
    if (startTime > endTime) {
      return currentTime >= startTime || currentTime <= endTime;
    } else {
      return currentTime >= startTime && currentTime <= endTime;
    }
  }

  /**
   * حساب وقت الجدولة
   */
  private calculateScheduleTime(): Date {
    const now = new Date();
    const endTime = this.config.quiet_hours.end;
    const [hours, minutes] = endTime.split(':').map(Number);

    const scheduleDate = new Date(now);
    scheduleDate.setHours(hours, minutes, 0, 0);

    // إذا كان الوقت قد مر لليوم، جدول للغد
    if (scheduleDate <= now) {
      scheduleDate.setDate(scheduleDate.getDate() + 1);
    }

    return scheduleDate;
  }

  /**
   * طلب صلاحيات الإشعارات
   */
  private async requestPermissions(): Promise<boolean> {
    try {
      console.log('📲 Requesting notification permissions...');
      
      // في التطبيق الحقيقي:
      // const permission = await PushNotification.requestPermissions();
      // return permission.alert && permission.sound;
      
      // محاكاة موافقة
      return true;

    } catch (error) {
      console.error('❌ Error requesting permissions:', error);
      return false;
    }
  }

  /**
   * تكوين push notifications
   */
  private configurePushNotifications(): void {
    // في التطبيق الحقيقي:
    // PushNotification.configure({
    //   onNotification: this.handleNotificationReceived.bind(this),
    //   permissions: {
    //     alert: true,
    //     badge: true,
    //     sound: true,
    //   },
    //   popInitialNotification: true,
    //   requestPermissions: true,
    // });

    console.log('⚙️ Push notifications configured');
  }

  /**
   * معالجة استلام إشعار
   */
  private handleNotificationReceived(notification: any): void {
    console.log('📩 Notification received:', notification);
    this.emit('notification_received', notification);
  }

  /**
   * إضافة للتاريخ
   */
  private addToHistory(notification: NotificationData): void {
    this.notificationHistory.unshift(notification);
    
    // الاحتفاظ بآخر 100 إشعار
    if (this.notificationHistory.length > 100) {
      this.notificationHistory = this.notificationHistory.slice(0, 100);
    }

    this.saveHistory();
  }

  /**
   * تحميل الإعدادات
   */
  private async loadConfig(): Promise<void> {
    try {
      const savedConfig = await AsyncStorage.getItem('notification_config');
      if (savedConfig) {
        this.config = { ...this.config, ...JSON.parse(savedConfig) };
      }
    } catch (error) {
      console.error('❌ Error loading notification config:', error);
    }
  }

  /**
   * حفظ الإعدادات
   */
  public async saveConfig(): Promise<void> {
    try {
      await AsyncStorage.setItem('notification_config', JSON.stringify(this.config));
    } catch (error) {
      console.error('❌ Error saving notification config:', error);
    }
  }

  /**
   * حفظ التاريخ
   */
  private async saveHistory(): Promise<void> {
    try {
      await AsyncStorage.setItem('notification_history', JSON.stringify(this.notificationHistory));
    } catch (error) {
      console.error('❌ Error saving notification history:', error);
    }
  }

  /**
   * تحميل التاريخ
   */
  private async loadHistory(): Promise<void> {
    try {
      const savedHistory = await AsyncStorage.getItem('notification_history');
      if (savedHistory) {
        this.notificationHistory = JSON.parse(savedHistory);
      }
    } catch (error) {
      console.error('❌ Error loading notification history:', error);
    }
  }

  /**
   * تسجيل إشعار حرج
   */
  private async logCriticalNotification(alert: Alert): Promise<void> {
    try {
      const criticalLog = await AsyncStorage.getItem('critical_notifications') || '[]';
      const logs = JSON.parse(criticalLog);
      
      logs.unshift({
        alert_id: alert.id,
        timestamp: new Date().toISOString(),
        type: alert.type,
        severity: alert.severity,
        handled: false
      });

      // الاحتفاظ بآخر 50 حالة حرجة
      if (logs.length > 50) {
        logs.splice(50);
      }

      await AsyncStorage.setItem('critical_notifications', JSON.stringify(logs));
    } catch (error) {
      console.error('❌ Error logging critical notification:', error);
    }
  }

  /**
   * الحصول على الإشعارات المجدولة
   */
  private async getScheduledNotifications(): Promise<any[]> {
    try {
      const scheduled = await AsyncStorage.getItem('scheduled_notifications');
      return scheduled ? JSON.parse(scheduled) : [];
    } catch (error) {
      console.error('❌ Error getting scheduled notifications:', error);
      return [];
    }
  }

  /**
   * تحديث إعدادات الإشعارات
   */
  public async updateConfig(newConfig: Partial<NotificationConfig>): Promise<void> {
    this.config = { ...this.config, ...newConfig };
    await this.saveConfig();
    this.emit('config_updated', this.config);
  }

  /**
   * الحصول على الإعدادات
   */
  public getConfig(): NotificationConfig {
    return { ...this.config };
  }

  /**
   * الحصول على التاريخ
   */
  public getHistory(): NotificationData[] {
    return [...this.notificationHistory];
  }

  /**
   * إحصائيات الإشعارات
   */
  public getStats() {
    return {
      total_sent: this.notificationHistory.length,
      config: this.config,
      is_initialized: this.isInitialized,
      quiet_time_active: this.isQuietTime()
    };
  }

  /**
   * تنظيف الموارد
   */
  public async cleanup(): Promise<void> {
    await this.saveConfig();
    await this.saveHistory();
    this.removeAllListeners();
    console.log('✅ NotificationService cleanup completed');
  }
}

export default NotificationService;
