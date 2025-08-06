/**
 * Alert Service - نظام التنبيهات الذكي والمراقبة اللحظية
 * 
 * Features:
 * - Real-time safety alerts via WebSocket
 * - Risk scoring and severity classification  
 * - Push notifications integration
 * - Alert history and resolution tracking
 * - COPPA-compliant alert handling
 * 
 * @version 1.0.0
 * @since 2025-08-04
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { EventEmitter } from 'events';
import { ApiService } from './api';
import { WebSocketService } from './WebSocketService';
import { NotificationService } from './NotificationService';

export interface Alert {
  id: string;
  child_id: string;
  child_name: string;
  type: 'forbidden_content' | 'self_harm' | 'excessive_usage' | 'inappropriate_interaction' | 'emergency';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  details: string;
  timestamp: string;
  resolved: boolean;
  resolved_at?: string;
  resolved_by?: string;
  risk_score: number; // 0-100
  auto_resolved: boolean;
  requires_immediate_action: boolean;
  escalation_level: number; // 1-4
  context?: {
    conversation_id?: string;
    message_content?: string;
    interaction_duration?: number;
    previous_warnings?: number;
  };
}

export interface AlertSummary {
  total_alerts: number;
  unresolved_alerts: number;
  critical_alerts: number;
  high_priority_alerts: number;
  alerts_today: number;
  alerts_this_week: number;
  most_common_type: string;
  trend: 'increasing' | 'decreasing' | 'stable';
}

export interface RiskAssessment {
  child_id: string;
  current_risk_level: 'low' | 'medium' | 'high' | 'critical';
  risk_factors: string[];
  recommended_actions: string[];
  monitoring_intensity: 'normal' | 'increased' | 'intensive';
  last_assessment: string;
}

export class AlertService extends EventEmitter {
  private static instance: AlertService;
  private webSocketService: WebSocketService;
  private notificationService: NotificationService;
  private alerts: Alert[] = [];
  private alertSummary: AlertSummary | null = null;
  private riskAssessments: Map<string, RiskAssessment> = new Map();
  private isMonitoring: boolean = false;
  private alertQueue: Alert[] = [];
  private processingQueue: boolean = false;

  private constructor() {
    super();
    this.webSocketService = WebSocketService.getInstance();
    this.notificationService = NotificationService.getInstance();
    this.setupEventHandlers();
  }

  public static getInstance(): AlertService {
    if (!AlertService.instance) {
      AlertService.instance = new AlertService();
    }
    return AlertService.instance;
  }

  /**
   * بدء نظام المراقبة اللحظية
   */
  public async startRealTimeMonitoring(): Promise<void> {
    try {
      console.log('🔴 Starting Real-Time Safety Monitoring...');
      
      // تحميل التنبيهات المحفوظة محلياً
      await this.loadCachedAlerts();
      
      // الاتصال بـ WebSocket للتنبيهات اللحظية
      await this.webSocketService.connect();
      
      // تسجيل مستمع التنبيهات
      this.webSocketService.on('safety_alert', this.handleIncomingAlert.bind(this));
      this.webSocketService.on('risk_assessment_update', this.handleRiskUpdate.bind(this));
      
      // جلب التنبيهات من السيرفر
      await this.fetchLatestAlerts();
      
      // تحديث ملخص التنبيهات
      await this.updateAlertSummary();
      
      this.isMonitoring = true;
      this.emit('monitoring_started');
      
      console.log('✅ Real-Time Monitoring Active');
    } catch (error) {
      console.error('❌ Failed to start monitoring:', error);
      this.emit('monitoring_error', error);
      throw error;
    }
  }

  /**
   * إيقاف نظام المراقبة
   */
  public async stopRealTimeMonitoring(): Promise<void> {
    try {
      console.log('⏹️ Stopping Real-Time Monitoring...');
      
      this.webSocketService.off('safety_alert', this.handleIncomingAlert.bind(this));
      this.webSocketService.off('risk_assessment_update', this.handleRiskUpdate.bind(this));
      await this.webSocketService.disconnect();
      
      this.isMonitoring = false;
      this.emit('monitoring_stopped');
      
      console.log('✅ Monitoring Stopped');
    } catch (error) {
      console.error('❌ Error stopping monitoring:', error);
    }
  }

  /**
   * معالجة التنبيه الواردة من السيرفر
   */
  private async handleIncomingAlert(alertData: any): Promise<void> {
    try {
      const alert: Alert = {
        id: alertData.id,
        child_id: alertData.child_id,
        child_name: alertData.child_name,
        type: alertData.type,
        severity: alertData.severity,
        message: alertData.message,
        details: alertData.details || '',
        timestamp: alertData.timestamp,
        resolved: false,
        risk_score: alertData.risk_score || 0,
        auto_resolved: false,
        requires_immediate_action: alertData.requires_immediate_action || false,
        escalation_level: alertData.escalation_level || 1,
        context: alertData.context
      };

      console.log('🚨 New Safety Alert Received:', alert);

      // إضافة التنبيه للقائمة
      this.addAlert(alert);

      // معالجة فورية للتنبيهات الحرجة
      if (alert.severity === 'critical' || alert.requires_immediate_action) {
        await this.handleCriticalAlert(alert);
      }

      // إرسال إشعار push
      await this.notificationService.sendAlertNotification(alert);

      // إشعار المستمعين
      this.emit('new_alert', alert);
      this.emit('alerts_updated', this.alerts);

    } catch (error) {
      console.error('❌ Error handling incoming alert:', error);
    }
  }

  /**
   * معالجة التنبيهات الحرجة
   */
  private async handleCriticalAlert(alert: Alert): Promise<void> {
    try {
      console.log('🚨 CRITICAL ALERT DETECTED:', alert);

      // تنبيه صوتي/اهتزازي فوري
      await this.notificationService.sendCriticalNotification(alert);

      // إضافة للقائمة العاجلة
      this.alertQueue.unshift(alert);

      // معالجة فورية
      if (!this.processingQueue) {
        await this.processAlertQueue();
      }

      // إشعار طارئ للمستمعين
      this.emit('critical_alert', alert);

      // تسجيل في سجل الطوارئ
      await this.logEmergencyAlert(alert);

    } catch (error) {
      console.error('❌ Error handling critical alert:', error);
    }
  }

  /**
   * معالجة قائمة التنبيهات العاجلة
   */
  private async processAlertQueue(): Promise<void> {
    this.processingQueue = true;

    try {
      while (this.alertQueue.length > 0) {
        const alert = this.alertQueue.shift();
        if (alert) {
          await this.processAlert(alert);
          await new Promise(resolve => setTimeout(resolve, 100)); // تأخير قصير
        }
      }
    } catch (error) {
      console.error('❌ Error processing alert queue:', error);
    } finally {
      this.processingQueue = false;
    }
  }

  /**
   * معالجة تنبيه واحد
   */
  private async processAlert(alert: Alert): Promise<void> {
    try {
      // تحديث تقييم المخاطر
      await this.updateRiskAssessment(alert.child_id, alert);

      // حفظ محلياً
      await this.saveAlertLocally(alert);

      // إشعار النظام
      this.emit('alert_processed', alert);

    } catch (error) {
      console.error('❌ Error processing alert:', error);
    }
  }

  /**
   * جلب آخر التنبيهات من السيرفر
   */
  public async fetchLatestAlerts(limit: number = 50): Promise<Alert[]> {
    try {
      console.log('📥 Fetching latest alerts from server...');
      
      const response = await ApiService.getSafetyAlerts();
      
      if (response && Array.isArray(response)) {
        this.alerts = response.map(alertData => ({
          id: alertData.id,
          child_id: alertData.child_id,
          child_name: alertData.child_name || 'Unknown',
          type: (alertData.type || 'inappropriate_interaction') as 'forbidden_content' | 'self_harm' | 'excessive_usage' | 'inappropriate_interaction' | 'emergency',
          severity: (alertData.severity || 'medium') as 'low' | 'medium' | 'high' | 'critical',
          message: alertData.message,
          details: alertData.details || '',
          timestamp: alertData.timestamp,
          resolved: alertData.resolved || false,
          resolved_at: alertData.resolved_at,
          resolved_by: alertData.resolved_by,
          risk_score: alertData.risk_score || 0,
          auto_resolved: alertData.auto_resolved || false,
          requires_immediate_action: alertData.requires_immediate_action || false,
          escalation_level: alertData.escalation_level || 1,
          context: alertData.context
        }));

        await this.cacheAlerts();
        this.emit('alerts_updated', this.alerts);
        
        console.log(`✅ Loaded ${this.alerts.length} alerts`);
      }

      return this.alerts;
    } catch (error) {
      console.error('❌ Error fetching alerts:', error);
      // استخدام التنبيهات المحفوظة محلياً في حالة الفشل
      await this.loadCachedAlerts();
      return this.alerts;
    }
  }

  /**
   * حل تنبيه (تأكيد المراجعة)
   */
  public async resolveAlert(alertId: string, resolvedBy: string): Promise<boolean> {
    try {
      console.log('✅ Resolving alert:', alertId);
      
      // تحديث محلياً
      const alertIndex = this.alerts.findIndex(a => a.id === alertId);
      if (alertIndex !== -1) {
        this.alerts[alertIndex].resolved = true;
        this.alerts[alertIndex].resolved_at = new Date().toISOString();
        this.alerts[alertIndex].resolved_by = resolvedBy;
      }

      // تحديث في السيرفر
      await ApiService.markSafetyAlertAsResolved(alertId);

      // حفظ محلياً
      await this.cacheAlerts();

      // تحديث الملخص
      await this.updateAlertSummary();

      this.emit('alert_resolved', alertId);
      this.emit('alerts_updated', this.alerts);

      return true;
    } catch (error) {
      console.error('❌ Error resolving alert:', error);
      return false;
    }
  }

  /**
   * الحصول على التنبيهات حسب الطفل
   */
  public getAlertsForChild(childId: string): Alert[] {
    return this.alerts.filter(alert => alert.child_id === childId);
  }

  /**
   * الحصول على التنبيهات غير المحلولة
   */
  public getUnresolvedAlerts(): Alert[] {
    return this.alerts.filter(alert => !alert.resolved);
  }

  /**
   * الحصول على التنبيهات الحرجة
   */
  public getCriticalAlerts(): Alert[] {
    return this.alerts.filter(alert => 
      alert.severity === 'critical' || alert.requires_immediate_action
    );
  }

  /**
   * الحصول على ملخص التنبيهات
   */
  public getAlertSummary(): AlertSummary | null {
    return this.alertSummary;
  }

  /**
   * الحصول على تقييم المخاطر لطفل
   */
  public getRiskAssessment(childId: string): RiskAssessment | null {
    return this.riskAssessments.get(childId) || null;
  }

  /**
   * تحديث ملخص التنبيهات
   */
  private async updateAlertSummary(): Promise<void> {
    try {
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

      const alertsToday = this.alerts.filter(alert => 
        new Date(alert.timestamp) >= today
      ).length;

      const alertsThisWeek = this.alerts.filter(alert => 
        new Date(alert.timestamp) >= weekAgo
      ).length;

      const unresolvedAlerts = this.getUnresolvedAlerts().length;
      const criticalAlerts = this.getCriticalAlerts().length;
      const highPriorityAlerts = this.alerts.filter(alert => 
        alert.severity === 'high' || alert.severity === 'critical'
      ).length;

      // تحديد النوع الأكثر شيوعاً
      const typeCounts = this.alerts.reduce((acc, alert) => {
        acc[alert.type] = (acc[alert.type] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);

      const mostCommonType = Object.keys(typeCounts).reduce((a, b) => 
        typeCounts[a] > typeCounts[b] ? a : b, 'none'
      );

      // تحديد الاتجاه
      const recentAlerts = this.alerts.filter(alert => 
        new Date(alert.timestamp) >= new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000)
      ).length;
      const olderAlerts = this.alerts.filter(alert => {
        const alertDate = new Date(alert.timestamp);
        return alertDate >= new Date(now.getTime() - 6 * 24 * 60 * 60 * 1000) &&
               alertDate < new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000);
      }).length;

      let trend: 'increasing' | 'decreasing' | 'stable' = 'stable';
      if (recentAlerts > olderAlerts * 1.2) trend = 'increasing';
      else if (recentAlerts < olderAlerts * 0.8) trend = 'decreasing';

      this.alertSummary = {
        total_alerts: this.alerts.length,
        unresolved_alerts: unresolvedAlerts,
        critical_alerts: criticalAlerts,
        high_priority_alerts: highPriorityAlerts,
        alerts_today: alertsToday,
        alerts_this_week: alertsThisWeek,
        most_common_type: mostCommonType,
        trend
      };

      this.emit('summary_updated', this.alertSummary);

    } catch (error) {
      console.error('❌ Error updating alert summary:', error);
    }
  }

  /**
   * تحديث تقييم المخاطر
   */
  private async updateRiskAssessment(childId: string, alert: Alert): Promise<void> {
    try {
      const childAlerts = this.getAlertsForChild(childId);
      const recentAlerts = childAlerts.filter(a => 
        new Date(a.timestamp) > new Date(Date.now() - 24 * 60 * 60 * 1000)
      );

      let riskLevel: 'low' | 'medium' | 'high' | 'critical' = 'low';
      const riskFactors: string[] = [];
      const recommendedActions: string[] = [];
      let monitoringIntensity: 'normal' | 'increased' | 'intensive' = 'normal';

      // تحليل المخاطر
      if (recentAlerts.length >= 5) {
        riskLevel = 'critical';
        riskFactors.push('Multiple alerts in 24 hours');
        recommendedActions.push('Immediate intervention required');
        monitoringIntensity = 'intensive';
      } else if (recentAlerts.length >= 3) {
        riskLevel = 'high';
        riskFactors.push('Frequent alerts');
        recommendedActions.push('Increased monitoring');
        monitoringIntensity = 'increased';
      } else if (alert.severity === 'critical') {
        riskLevel = 'high';
        riskFactors.push('Critical safety concern');
        recommendedActions.push('Review interaction immediately');
        monitoringIntensity = 'increased';
      }

      // تحليل أنواع التنبيهات
      const alertTypes = childAlerts.map(a => a.type);
      if (alertTypes.includes('self_harm')) {
        riskLevel = 'critical';
        riskFactors.push('Self-harm indicators detected');
        recommendedActions.push('Contact mental health professional');
      }

      if (alertTypes.includes('forbidden_content')) {
        riskFactors.push('Exposure to inappropriate content');
        recommendedActions.push('Review content filters');
      }

      const assessment: RiskAssessment = {
        child_id: childId,
        current_risk_level: riskLevel,
        risk_factors: riskFactors,
        recommended_actions: recommendedActions,
        monitoring_intensity: monitoringIntensity,
        last_assessment: new Date().toISOString()
      };

      this.riskAssessments.set(childId, assessment);
      this.emit('risk_assessment_updated', assessment);

    } catch (error) {
      console.error('❌ Error updating risk assessment:', error);
    }
  }

  /**
   * إضافة تنبيه جديد (عام للاستخدام الخارجي)
   */
  public addNewAlert(alert: Alert): void {
    this.addAlert(alert);
    this.emit('new_alert', alert);
    this.emit('alerts_updated', this.alerts);
  }

  /**
   * إضافة تنبيه جديد (خاص)
   */
  private addAlert(alert: Alert): void {
    // تجنب التكرار
    const existingIndex = this.alerts.findIndex(a => a.id === alert.id);
    if (existingIndex !== -1) {
      this.alerts[existingIndex] = alert;
    } else {
      this.alerts.unshift(alert); // إضافة في البداية
    }

    // الحفاظ على حد أقصى من التنبيهات
    if (this.alerts.length > 1000) {
      this.alerts = this.alerts.slice(0, 1000);
    }
  }

  /**
   * حفظ التنبيهات محلياً
   */
  private async cacheAlerts(): Promise<void> {
    try {
      await AsyncStorage.setItem('cached_alerts', JSON.stringify(this.alerts));
      await AsyncStorage.setItem('alert_summary', JSON.stringify(this.alertSummary));
    } catch (error) {
      console.error('❌ Error caching alerts:', error);
    }
  }

  /**
   * تحميل التنبيهات المحفوظة
   */
  private async loadCachedAlerts(): Promise<void> {
    try {
      const cachedAlerts = await AsyncStorage.getItem('cached_alerts');
      const cachedSummary = await AsyncStorage.getItem('alert_summary');

      if (cachedAlerts) {
        this.alerts = JSON.parse(cachedAlerts);
      }

      if (cachedSummary) {
        this.alertSummary = JSON.parse(cachedSummary);
      }

      console.log(`📱 Loaded ${this.alerts.length} cached alerts`);
    } catch (error) {
      console.error('❌ Error loading cached alerts:', error);
    }
  }

  /**
   * حفظ تنبيه محلياً
   */
  private async saveAlertLocally(alert: Alert): Promise<void> {
    try {
      const existingAlerts = await AsyncStorage.getItem('local_alerts') || '[]';
      const alerts = JSON.parse(existingAlerts);
      alerts.unshift(alert);
      
      // الاحتفاظ بآخر 100 تنبيه محلياً
      if (alerts.length > 100) {
        alerts.splice(100);
      }
      
      await AsyncStorage.setItem('local_alerts', JSON.stringify(alerts));
    } catch (error) {
      console.error('❌ Error saving alert locally:', error);
    }
  }

  /**
   * تسجيل تنبيه طارئ
   */
  private async logEmergencyAlert(alert: Alert): Promise<void> {
    try {
      const emergencyLog = await AsyncStorage.getItem('emergency_alerts') || '[]';
      const logs = JSON.parse(emergencyLog);
      
      logs.unshift({
        alert_id: alert.id,
        timestamp: new Date().toISOString(),
        severity: alert.severity,
        type: alert.type,
        child_id: alert.child_id
      });

      // الاحتفاظ بآخر 50 حالة طارئة
      if (logs.length > 50) {
        logs.splice(50);
      }

      await AsyncStorage.setItem('emergency_alerts', JSON.stringify(logs));
    } catch (error) {
      console.error('❌ Error logging emergency alert:', error);
    }
  }

  /**
   * معالجة تحديث تقييم المخاطر من السيرفر
   */
  private handleRiskUpdate(data: any): void {
    try {
      const assessment: RiskAssessment = {
        child_id: data.child_id,
        current_risk_level: data.risk_level,
        risk_factors: data.risk_factors || [],
        recommended_actions: data.recommended_actions || [],
        monitoring_intensity: data.monitoring_intensity || 'normal',
        last_assessment: data.timestamp
      };

      this.riskAssessments.set(data.child_id, assessment);
      this.emit('risk_assessment_updated', assessment);
    } catch (error) {
      console.error('❌ Error handling risk update:', error);
    }
  }

  /**
   * إعداد معالجات الأحداث
   */
  private setupEventHandlers(): void {
    // معالج إعادة الاتصال
    this.webSocketService.on('reconnected', async () => {
      console.log('🔄 WebSocket reconnected, refreshing alerts...');
      await this.fetchLatestAlerts();
    });

    // معالج أخطاء الاتصال
    this.webSocketService.on('connection_error', (error) => {
      console.error('❌ WebSocket connection error:', error);
      this.emit('monitoring_error', error);
    });
  }

  /**
   * إحصائيات المراقبة
   */
  public getMonitoringStats() {
    return {
      is_monitoring: this.isMonitoring,
      total_alerts: this.alerts.length,
      unresolved_count: this.getUnresolvedAlerts().length,
      critical_count: this.getCriticalAlerts().length,
      queue_length: this.alertQueue.length,
      processing_queue: this.processingQueue,
      websocket_connected: this.webSocketService.isConnected(),
      last_update: new Date().toISOString()
    };
  }

  /**
   * تنظيف الموارد
   */
  public async cleanup(): Promise<void> {
    try {
      await this.stopRealTimeMonitoring();
      await this.cacheAlerts();
      this.removeAllListeners();
      console.log('✅ AlertService cleanup completed');
    } catch (error) {
      console.error('❌ Error during cleanup:', error);
    }
  }
}

export default AlertService;
