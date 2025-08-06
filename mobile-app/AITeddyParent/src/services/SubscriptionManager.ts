/**
 * Subscription Manager - إدارة الاشتراكات والميزات المميزة
 * 
 * Features:
 * - Multi-tier subscription management
 * - Iraqi payment methods integration
 * - Feature access control
 * - Usage tracking and limits
 * - Trial period management
 * - COPPA-compliant billing
 * 
 * @version 1.0.0
 * @since 2025-08-04
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { EventEmitter } from 'events';
import { ApiService } from './api';
import { AlertService } from './AlertService';

export interface SubscriptionPlan {
  id: string;
  name: string;
  name_ar: string;
  description: string;
  description_ar: string;
  price_usd: number;
  price_iqd: number;
  billing_cycle: 'monthly' | 'quarterly' | 'yearly';
  features: PlanFeature[];
  limits: UsageLimits;
  is_popular: boolean;
  is_trial_available: boolean;
  trial_days: number;
}

export interface PlanFeature {
  id: string;
  name: string;
  name_ar: string;
  description: string;
  description_ar: string;
  enabled: boolean;
  category: 'safety' | 'monitoring' | 'reports' | 'storage' | 'support';
}

export interface UsageLimits {
  max_children: number;
  max_daily_interactions: number;
  max_monthly_reports: number;
  max_storage_mb: number;
  max_alert_history_days: number;
  real_time_monitoring: boolean;
  ai_insights: boolean;
  priority_support: boolean;
  data_export: boolean;
}

export interface UserSubscription {
  id: string;
  user_id: string;
  plan_id: string;
  plan_name: string;
  status: 'active' | 'expired' | 'cancelled' | 'pending' | 'trial';
  start_date: string;
  end_date: string;
  next_billing_date?: string;
  payment_method: PaymentMethod;
  auto_renew: boolean;
  trial_used: boolean;
  cancellation_reason?: string;
  upgrade_available: boolean;
}

export interface PaymentMethod {
  id: string;
  type: 'credit_card' | 'bank_transfer' | 'mobile_wallet' | 'paypal' | 'zaincash' | 'asiacell';
  provider: string;
  last_four?: string;
  expiry_month?: number;
  expiry_year?: number;
  holder_name?: string;
  is_default: boolean;
  verified: boolean;
  supported_in_iraq: boolean;
}

export interface UsageStats {
  current_period_start: string;
  current_period_end: string;
  children_count: number;
  daily_interactions_used: number;
  monthly_reports_generated: number;
  storage_used_mb: number;
  features_accessed: string[];
  last_updated: string;
}

export interface BillingHistory {
  id: string;
  subscription_id: string;
  amount_usd: number;
  amount_iqd: number;
  currency: 'USD' | 'IQD';
  payment_date: string;
  payment_method: string;
  status: 'paid' | 'pending' | 'failed' | 'refunded';
  invoice_url?: string;
  receipt_url?: string;
}

export class SubscriptionManager extends EventEmitter {
  private static instance: SubscriptionManager;
  private alertService: AlertService;
  private availablePlans: SubscriptionPlan[] = [];
  private currentSubscription: UserSubscription | null = null;
  private usageStats: UsageStats | null = null;
  private billingHistory: BillingHistory[] = [];
  private featureAccess: Map<string, boolean> = new Map();

  private constructor() {
    super();
    this.alertService = AlertService.getInstance();
    this.initializeDefaultPlans();
    this.loadSubscriptionData();
  }

  public static getInstance(): SubscriptionManager {
    if (!SubscriptionManager.instance) {
      SubscriptionManager.instance = new SubscriptionManager();
    }
    return SubscriptionManager.instance;
  }

  /**
   * تهيئة خطط الاشتراك الافتراضية
   */
  private initializeDefaultPlans(): void {
    this.availablePlans = [
      {
        id: 'free',
        name: 'Free Plan',
        name_ar: 'الخطة المجانية',
        description: 'Basic safety monitoring for one child',
        description_ar: 'مراقبة أساسية للأمان لطفل واحد',
        price_usd: 0,
        price_iqd: 0,
        billing_cycle: 'monthly',
        features: this.getFreeFeatures(),
        limits: {
          max_children: 1,
          max_daily_interactions: 50,
          max_monthly_reports: 1,
          max_storage_mb: 100,
          max_alert_history_days: 7,
          real_time_monitoring: false,
          ai_insights: false,
          priority_support: false,
          data_export: false
        },
        is_popular: false,
        is_trial_available: false,
        trial_days: 0
      },
      {
        id: 'basic',
        name: 'Basic Plan',
        name_ar: 'الخطة الأساسية',
        description: 'Enhanced monitoring for up to 3 children',
        description_ar: 'مراقبة محسنة لحتى 3 أطفال',
        price_usd: 9.99,
        price_iqd: 15000,
        billing_cycle: 'monthly',
        features: this.getBasicFeatures(),
        limits: {
          max_children: 3,
          max_daily_interactions: 200,
          max_monthly_reports: 5,
          max_storage_mb: 500,
          max_alert_history_days: 30,
          real_time_monitoring: true,
          ai_insights: false,
          priority_support: false,
          data_export: true
        },
        is_popular: true,
        is_trial_available: true,
        trial_days: 7
      },
      {
        id: 'premium',
        name: 'Premium Plan',
        name_ar: 'الخطة المميزة',
        description: 'Advanced AI monitoring for unlimited children',
        description_ar: 'مراقبة ذكية متقدمة لعدد غير محدود من الأطفال',
        price_usd: 19.99,
        price_iqd: 30000,
        billing_cycle: 'monthly',
        features: this.getPremiumFeatures(),
        limits: {
          max_children: -1, // unlimited
          max_daily_interactions: -1, // unlimited
          max_monthly_reports: -1, // unlimited
          max_storage_mb: 5000,
          max_alert_history_days: 365,
          real_time_monitoring: true,
          ai_insights: true,
          priority_support: true,
          data_export: true
        },
        is_popular: false,
        is_trial_available: true,
        trial_days: 14
      }
    ];
  }

  /**
   * الحصول على جميع خطط الاشتراك
   */
  public async getAvailablePlans(): Promise<SubscriptionPlan[]> {
    try {
      // محاولة جلب الخطط من السيرفر
      const serverPlans = await this.fetchPlansFromServer();
      if (serverPlans && serverPlans.length > 0) {
        this.availablePlans = serverPlans;
      }

      return this.availablePlans;
    } catch (error) {
      console.error('❌ Error fetching plans:', error);
      return this.availablePlans; // استخدام الخطط الافتراضية
    }
  }

  /**
   * الحصول على الاشتراك الحالي
   */
  public async getCurrentSubscription(): Promise<UserSubscription | null> {
    try {
      if (!this.currentSubscription) {
        await this.loadSubscriptionData();
      }

      // التحقق من انتهاء الاشتراك
      if (this.currentSubscription && this.isSubscriptionExpired(this.currentSubscription)) {
        await this.handleExpiredSubscription();
      }

      return this.currentSubscription;
    } catch (error) {
      console.error('❌ Error getting current subscription:', error);
      return null;
    }
  }

  /**
   * بدء فترة تجريبية
   */
  public async startTrial(planId: string): Promise<boolean> {
    try {
      console.log('🎯 Starting trial for plan:', planId);

      const plan = this.availablePlans.find(p => p.id === planId);
      if (!plan) {
        throw new Error('Plan not found');
      }

      if (!plan.is_trial_available) {
        throw new Error('Trial not available for this plan');
      }

      if (this.currentSubscription?.trial_used) {
        throw new Error('Trial already used');
      }

      const trialEndDate = new Date();
      trialEndDate.setDate(trialEndDate.getDate() + plan.trial_days);

      const trialSubscription: UserSubscription = {
        id: `trial_${Date.now()}`,
        user_id: 'current_user', // سيتم تحديثه من الجلسة
        plan_id: planId,
        plan_name: plan.name_ar,
        status: 'trial',
        start_date: new Date().toISOString(),
        end_date: trialEndDate.toISOString(),
        payment_method: {
          id: 'trial',
          type: 'credit_card',
          provider: 'trial',
          is_default: false,
          verified: true,
          supported_in_iraq: true
        },
        auto_renew: false,
        trial_used: true,
        upgrade_available: true
      };

      await this.setCurrentSubscription(trialSubscription);
      this.emit('trial_started', { plan, subscription: trialSubscription });

      // إنشاء تنبيه للفترة التجريبية
      this.alertService.addNewAlert({
        id: `alert_${Date.now()}`,
        child_id: 'system',
        child_name: 'النظام',
        type: 'inappropriate_interaction',
        severity: 'medium',
        message: `بدأت الفترة التجريبية للخطة ${plan.name_ar}`,
        details: `ستنتهي الفترة التجريبية في ${trialEndDate.toLocaleDateString('ar-EG')}`,
        timestamp: new Date().toISOString(),
        resolved: false,
        risk_score: 10,
        auto_resolved: false,
        requires_immediate_action: false,
        escalation_level: 1
      });

      console.log('✅ Trial started successfully');
      return true;

    } catch (error) {
      console.error('❌ Error starting trial:', error);
      throw error;
    }
  }

  /**
   * ترقية الاشتراك
   */
  public async upgradeSubscription(
    newPlanId: string, 
    paymentMethod: PaymentMethod
  ): Promise<boolean> {
    try {
      console.log('⬆️ Upgrading subscription to plan:', newPlanId);

      const newPlan = this.availablePlans.find(p => p.id === newPlanId);
      if (!newPlan) {
        throw new Error('Plan not found');
      }

      // التحقق من صحة طريقة الدفع
      if (!this.validatePaymentMethod(paymentMethod)) {
        throw new Error('Invalid payment method');
      }

      // حساب تاريخ انتهاء الاشتراك الجديد
      const startDate = new Date();
      const endDate = this.calculateEndDate(startDate, newPlan.billing_cycle);
      const nextBilling = this.calculateNextBilling(endDate, newPlan.billing_cycle);

      const newSubscription: UserSubscription = {
        id: `sub_${Date.now()}`,
        user_id: 'current_user',
        plan_id: newPlanId,
        plan_name: newPlan.name_ar,
        status: 'active',
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
        next_billing_date: nextBilling.toISOString(),
        payment_method: paymentMethod,
        auto_renew: true,
        trial_used: this.currentSubscription?.trial_used || false,
        upgrade_available: newPlanId !== 'premium'
      };

      // محاكاة معالجة الدفع
      const paymentSuccess = await this.processPayment(newPlan, paymentMethod);
      if (!paymentSuccess) {
        throw new Error('Payment processing failed');
      }

      await this.setCurrentSubscription(newSubscription);
      this.emit('subscription_upgraded', { 
        oldPlan: this.currentSubscription?.plan_id, 
        newPlan: newPlanId 
      });

      console.log('✅ Subscription upgraded successfully');
      return true;

    } catch (error) {
      console.error('❌ Error upgrading subscription:', error);
      throw error;
    }
  }

  /**
   * إلغاء الاشتراك
   */
  public async cancelSubscription(reason?: string): Promise<boolean> {
    try {
      console.log('❌ Cancelling subscription');

      if (!this.currentSubscription) {
        throw new Error('No active subscription found');
      }

      const updatedSubscription = {
        ...this.currentSubscription,
        status: 'cancelled' as const,
        auto_renew: false,
        cancellation_reason: reason
      };

      await this.setCurrentSubscription(updatedSubscription);
      this.emit('subscription_cancelled', { reason, subscription: updatedSubscription });

      // إنشاء تنبيه للإلغاء
      this.alertService.addNewAlert({
        id: `alert_${Date.now()}`,
        child_id: 'system',
        child_name: 'النظام',
        type: 'inappropriate_interaction',
        severity: 'medium',
        message: 'تم إلغاء الاشتراك',
        details: reason || 'لم يتم تحديد سبب الإلغاء',
        timestamp: new Date().toISOString(),
        resolved: false,
        risk_score: 15,
        auto_resolved: false,
        requires_immediate_action: false,
        escalation_level: 1
      });

      console.log('✅ Subscription cancelled successfully');
      return true;

    } catch (error) {
      console.error('❌ Error cancelling subscription:', error);
      throw error;
    }
  }

  /**
   * التحقق من صلاحية الوصول لميزة
   */
  public hasFeatureAccess(featureId: string): boolean {
    try {
      if (!this.currentSubscription) {
        return this.isFreeFeature(featureId);
      }

      if (this.currentSubscription.status !== 'active' && this.currentSubscription.status !== 'trial') {
        return this.isFreeFeature(featureId);
      }

      const plan = this.availablePlans.find(p => p.id === this.currentSubscription?.plan_id);
      if (!plan) {
        return false;
      }

      return plan.features.some(f => f.id === featureId && f.enabled);

    } catch (error) {
      console.error('❌ Error checking feature access:', error);
      return false;
    }
  }

  /**
   * التحقق من حدود الاستخدام
   */
  public async checkUsageLimit(limitType: keyof UsageLimits, currentUsage: number): Promise<boolean> {
    try {
      if (!this.currentSubscription) {
        const freeLimit = this.getFreeLimit(limitType);
        return currentUsage < freeLimit;
      }

      const plan = this.availablePlans.find(p => p.id === this.currentSubscription?.plan_id);
      if (!plan) {
        return false;
      }

      const limit = plan.limits[limitType];
      
      // -1 يعني لا توجد حدود
      if (typeof limit === 'number' && limit === -1) {
        return true;
      }

      if (typeof limit === 'number') {
        return currentUsage < limit;
      }

      return Boolean(limit);

    } catch (error) {
      console.error('❌ Error checking usage limit:', error);
      return false;
    }
  }

  /**
   * تحديث إحصائيات الاستخدام
   */
  public async updateUsageStats(stats: Partial<UsageStats>): Promise<void> {
    try {
      if (!this.usageStats) {
        this.usageStats = this.createDefaultUsageStats();
      }

      this.usageStats = {
        ...this.usageStats,
        ...stats,
        last_updated: new Date().toISOString()
      };

      await AsyncStorage.setItem('usage_stats', JSON.stringify(this.usageStats));
      this.emit('usage_updated', this.usageStats);

      // التحقق من اقتراب حدود الاستخدام
      await this.checkUsageLimits();

    } catch (error) {
      console.error('❌ Error updating usage stats:', error);
    }
  }

  /**
   * الحصول على إحصائيات الاستخدام
   */
  public getUsageStats(): UsageStats | null {
    return this.usageStats;
  }

  /**
   * الحصول على تاريخ الفواتير
   */
  public async getBillingHistory(): Promise<BillingHistory[]> {
    try {
      if (this.billingHistory.length === 0) {
        await this.loadBillingHistory();
      }

      return this.billingHistory.sort((a, b) => 
        new Date(b.payment_date).getTime() - new Date(a.payment_date).getTime()
      );

    } catch (error) {
      console.error('❌ Error getting billing history:', error);
      return [];
    }
  }

  /**
   * دوال مساعدة خاصة
   */
  private async loadSubscriptionData(): Promise<void> {
    try {
      const stored = await AsyncStorage.getItem('current_subscription');
      if (stored) {
        this.currentSubscription = JSON.parse(stored);
      }

      const usageStored = await AsyncStorage.getItem('usage_stats');
      if (usageStored) {
        this.usageStats = JSON.parse(usageStored);
      } else {
        this.usageStats = this.createDefaultUsageStats();
      }

    } catch (error) {
      console.error('❌ Error loading subscription data:', error);
    }
  }

  private async setCurrentSubscription(subscription: UserSubscription): Promise<void> {
    this.currentSubscription = subscription;
    await AsyncStorage.setItem('current_subscription', JSON.stringify(subscription));
    this.updateFeatureAccess();
  }

  private updateFeatureAccess(): void {
    this.featureAccess.clear();

    if (!this.currentSubscription) {
      this.getFreeFeatures().forEach(feature => {
        this.featureAccess.set(feature.id, feature.enabled);
      });
      return;
    }

    const plan = this.availablePlans.find(p => p.id === this.currentSubscription?.plan_id);
    if (plan) {
      plan.features.forEach(feature => {
        this.featureAccess.set(feature.id, feature.enabled);
      });
    }
  }

  private isSubscriptionExpired(subscription: UserSubscription): boolean {
    return new Date() > new Date(subscription.end_date);
  }

  private async handleExpiredSubscription(): Promise<void> {
    if (this.currentSubscription) {
      this.currentSubscription.status = 'expired';
      await this.setCurrentSubscription(this.currentSubscription);
      this.emit('subscription_expired', this.currentSubscription);

      // إنشاء تنبيه لانتهاء الاشتراك
      this.alertService.addNewAlert({
        id: `alert_${Date.now()}`,
        child_id: 'system',
        child_name: 'النظام',
        type: 'inappropriate_interaction',
        severity: 'high',
        message: 'انتهت صلاحية الاشتراك',
        details: 'يرجى تجديد الاشتراك للاستمرار في استخدام الميزات المميزة',
        timestamp: new Date().toISOString(),
        resolved: false,
        risk_score: 25,
        auto_resolved: false,
        requires_immediate_action: true,
        escalation_level: 2
      });
    }
  }

  private validatePaymentMethod(paymentMethod: PaymentMethod): boolean {
    if (!paymentMethod.supported_in_iraq) {
      return false;
    }

    if (!paymentMethod.verified) {
      return false;
    }

    // التحقق من انتهاء صلاحية البطاقة
    if (paymentMethod.type === 'credit_card' && paymentMethod.expiry_month && paymentMethod.expiry_year) {
      const expiry = new Date(paymentMethod.expiry_year, paymentMethod.expiry_month - 1);
      if (expiry < new Date()) {
        return false;
      }
    }

    return true;
  }

  private calculateEndDate(startDate: Date, billingCycle: string): Date {
    const endDate = new Date(startDate);

    switch (billingCycle) {
      case 'monthly':
        endDate.setMonth(endDate.getMonth() + 1);
        break;
      case 'quarterly':
        endDate.setMonth(endDate.getMonth() + 3);
        break;
      case 'yearly':
        endDate.setFullYear(endDate.getFullYear() + 1);
        break;
    }

    return endDate;
  }

  private calculateNextBilling(endDate: Date, billingCycle: string): Date {
    return this.calculateEndDate(endDate, billingCycle);
  }

  private async processPayment(plan: SubscriptionPlan, paymentMethod: PaymentMethod): Promise<boolean> {
    // محاكاة معالجة الدفع
    console.log('💳 Processing payment for plan:', plan.name_ar);
    console.log('💳 Payment method:', paymentMethod.type);

    // في التطبيق الحقيقي سيتم التكامل مع بوابات الدفع العراقية
    await new Promise(resolve => setTimeout(resolve, 2000));

    // محاكاة نجاح الدفع (95% نسبة نجاح)
    const success = Math.random() > 0.05;

    if (success) {
      // إضافة سجل فاتورة جديد
      const billing: BillingHistory = {
        id: `bill_${Date.now()}`,
        subscription_id: this.currentSubscription?.id || '',
        amount_usd: plan.price_usd,
        amount_iqd: plan.price_iqd,
        currency: 'IQD',
        payment_date: new Date().toISOString(),
        payment_method: paymentMethod.provider,
        status: 'paid'
      };

      this.billingHistory.unshift(billing);
      await this.saveBillingHistory();
    }

    return success;
  }

  private async fetchPlansFromServer(): Promise<SubscriptionPlan[] | null> {
    try {
      // محاكاة جلب الخطط من السيرفر
      await new Promise(resolve => setTimeout(resolve, 1000));
      return null; // سيتم تنفيذها لاحقاً
    } catch (error) {
      console.error('❌ Error fetching plans from server:', error);
      return null;
    }
  }

  private getFreeFeatures(): PlanFeature[] {
    return [
      {
        id: 'basic_monitoring',
        name: 'Basic Monitoring',
        name_ar: 'المراقبة الأساسية',
        description: 'Basic safety monitoring',
        description_ar: 'مراقبة أساسية للأمان',
        enabled: true,
        category: 'safety'
      },
      {
        id: 'daily_reports',
        name: 'Daily Reports',
        name_ar: 'التقارير اليومية',
        description: 'Basic daily usage reports',
        description_ar: 'تقارير يومية أساسية للاستخدام',
        enabled: true,
        category: 'reports'
      }
    ];
  }

  private getBasicFeatures(): PlanFeature[] {
    return [
      ...this.getFreeFeatures(),
      {
        id: 'real_time_alerts',
        name: 'Real-time Alerts',
        name_ar: 'التنبيهات اللحظية',
        description: 'Instant safety alerts',
        description_ar: 'تنبيهات أمان فورية',
        enabled: true,
        category: 'safety'
      },
      {
        id: 'weekly_reports',
        name: 'Weekly Reports',
        name_ar: 'التقارير الأسبوعية',
        description: 'Detailed weekly reports',
        description_ar: 'تقارير أسبوعية مفصلة',
        enabled: true,
        category: 'reports'
      },
      {
        id: 'data_export',
        name: 'Data Export',
        name_ar: 'تصدير البيانات',
        description: 'Export your data',
        description_ar: 'تصدير بياناتك',
        enabled: true,
        category: 'storage'
      }
    ];
  }

  private getPremiumFeatures(): PlanFeature[] {
    return [
      ...this.getBasicFeatures(),
      {
        id: 'ai_insights',
        name: 'AI Insights',
        name_ar: 'رؤى الذكاء الاصطناعي',
        description: 'Advanced AI analysis',
        description_ar: 'تحليل متقدم بالذكاء الاصطناعي',
        enabled: true,
        category: 'monitoring'
      },
      {
        id: 'priority_support',
        name: 'Priority Support',
        name_ar: 'الدعم المميز',
        description: '24/7 priority support',
        description_ar: 'دعم مميز على مدار الساعة',
        enabled: true,
        category: 'support'
      },
      {
        id: 'unlimited_storage',
        name: 'Unlimited Storage',
        name_ar: 'تخزين غير محدود',
        description: 'Unlimited data storage',
        description_ar: 'تخزين غير محدود للبيانات',
        enabled: true,
        category: 'storage'
      }
    ];
  }

  private isFreeFeature(featureId: string): boolean {
    return this.getFreeFeatures().some(f => f.id === featureId && f.enabled);
  }

  private getFreeLimit(limitType: keyof UsageLimits): number {
    const freeLimits = this.availablePlans.find(p => p.id === 'free')?.limits;
    if (!freeLimits) return 0;

    const limit = freeLimits[limitType];
    return typeof limit === 'number' ? limit : 0;
  }

  private createDefaultUsageStats(): UsageStats {
    const now = new Date();
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);

    return {
      current_period_start: startOfMonth.toISOString(),
      current_period_end: endOfMonth.toISOString(),
      children_count: 0,
      daily_interactions_used: 0,
      monthly_reports_generated: 0,
      storage_used_mb: 0,
      features_accessed: [],
      last_updated: now.toISOString()
    };
  }

  private async checkUsageLimits(): Promise<void> {
    if (!this.usageStats || !this.currentSubscription) return;

    const plan = this.availablePlans.find(p => p.id === this.currentSubscription?.plan_id);
    if (!plan) return;

    // التحقق من حدود الأطفال
    if (plan.limits.max_children !== -1 && 
        this.usageStats.children_count >= plan.limits.max_children * 0.8) {
      this.emit('usage_warning', {
        type: 'children_limit',
        current: this.usageStats.children_count,
        limit: plan.limits.max_children
      });
    }

    // التحقق من حدود التخزين
    if (this.usageStats.storage_used_mb >= plan.limits.max_storage_mb * 0.8) {
      this.emit('usage_warning', {
        type: 'storage_limit',
        current: this.usageStats.storage_used_mb,
        limit: plan.limits.max_storage_mb
      });
    }
  }

  private async loadBillingHistory(): Promise<void> {
    try {
      const stored = await AsyncStorage.getItem('billing_history');
      if (stored) {
        this.billingHistory = JSON.parse(stored);
      }
    } catch (error) {
      console.error('❌ Error loading billing history:', error);
    }
  }

  private async saveBillingHistory(): Promise<void> {
    try {
      await AsyncStorage.setItem('billing_history', JSON.stringify(this.billingHistory));
    } catch (error) {
      console.error('❌ Error saving billing history:', error);
    }
  }

  /**
   * تنظيف الموارد
   */
  public async cleanup(): Promise<void> {
    this.currentSubscription = null;
    this.usageStats = null;
    this.billingHistory = [];
    this.featureAccess.clear();
    this.removeAllListeners();
    
    console.log('✅ SubscriptionManager cleanup completed');
  }
}

export default SubscriptionManager;
