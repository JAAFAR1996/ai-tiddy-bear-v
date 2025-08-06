/**
 * Multi-Child Manager - إدارة عدة أطفال بأمان وخصوصية
 * 
 * Features:
 * - Secure child profile management
 * - Individual privacy settings
 * - Access permission system
 * - Child switching with authentication
 * - COPPA-compliant data isolation
 * - Emergency contact management
 * 
 * @version 1.0.0
 * @since 2025-08-04
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { EventEmitter } from 'events';
import { ApiService } from './api';
import { AlertService } from './AlertService';

export interface ChildProfile {
  id: string;
  name: string;
  age: number;
  avatar_url?: string;
  date_of_birth: string;
  grade_level?: string;
  privacy_settings: ChildPrivacySettings;
  emergency_contacts: EmergencyContact[];
  parent_permissions: ParentPermissions;
  safety_preferences: SafetyPreferences;
  created_at: string;
  last_accessed: string;
  is_active: boolean;
  backup_parent_email?: string;
}

export interface ChildPrivacySettings {
  data_sharing: boolean;
  analytics_enabled: boolean;
  interaction_logging: boolean;
  external_communication: boolean;
  location_access: boolean;
  camera_access: boolean;
  microphone_access: boolean;
  report_sharing: boolean;
}

export interface EmergencyContact {
  id: string;
  name: string;
  relationship: string;
  phone: string;
  email: string;
  is_primary: boolean;
  can_receive_alerts: boolean;
}

export interface ParentPermissions {
  can_view_interactions: boolean;
  can_modify_settings: boolean;
  can_delete_data: boolean;
  can_share_reports: boolean;
  requires_pin_for_access: boolean;
  pin_hash?: string;
  session_timeout_minutes: number;
  two_factor_enabled: boolean;
}

export interface SafetyPreferences {
  content_filter_level: 'low' | 'medium' | 'high' | 'maximum';
  time_restrictions: TimeRestriction[];
  allowed_topics: string[];
  blocked_topics: string[];
  emergency_keywords: string[];
  auto_alert_enabled: boolean;
  parent_notification_level: 'all' | 'critical_only' | 'none';
}

export interface TimeRestriction {
  day_of_week: number; // 0-6 (Sunday-Saturday)
  start_time: string; // HH:MM format
  end_time: string; // HH:MM format
  max_duration_minutes: number;
  break_interval_minutes: number;
}

export interface ChildSession {
  child_id: string;
  session_start: string;
  session_timeout: string;
  authenticated: boolean;
  permissions_granted: string[];
}

export class MultiChildManager extends EventEmitter {
  private static instance: MultiChildManager;
  private alertService: AlertService;
  private childProfiles: Map<string, ChildProfile> = new Map();
  private activeChildId: string | null = null;
  private currentSession: ChildSession | null = null;
  private sessionTimer: NodeJS.Timeout | null = null;

  private constructor() {
    super();
    this.alertService = AlertService.getInstance();
    this.loadStoredProfiles();
  }

  public static getInstance(): MultiChildManager {
    if (!MultiChildManager.instance) {
      MultiChildManager.instance = new MultiChildManager();
    }
    return MultiChildManager.instance;
  }

  /**
   * إنشاء ملف تعريف طفل جديد
   */
  public async createChildProfile(childData: Partial<ChildProfile>): Promise<ChildProfile> {
    try {
      console.log('👶 Creating new child profile:', childData.name);

      // التحقق من صحة البيانات
      this.validateChildData(childData);

      // إنشاء الملف التعريفي الجديد
      const newChild: ChildProfile = {
        id: `child_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        name: childData.name || '',
        age: childData.age || 0,
        avatar_url: childData.avatar_url,
        date_of_birth: childData.date_of_birth || '',
        grade_level: childData.grade_level,
        privacy_settings: childData.privacy_settings || this.getDefaultPrivacySettings(),
        emergency_contacts: childData.emergency_contacts || [],
        parent_permissions: childData.parent_permissions || this.getDefaultParentPermissions(),
        safety_preferences: childData.safety_preferences || this.getDefaultSafetyPreferences(),
        created_at: new Date().toISOString(),
        last_accessed: new Date().toISOString(),
        is_active: true,
        backup_parent_email: childData.backup_parent_email
      };

      // حفظ الملف التعريفي
      await this.saveChildProfile(newChild);

      // إشعار بالإنشاء
      this.emit('child_profile_created', newChild);

      // إنشاء تنبيه للوالدين
      this.alertService.addNewAlert({
        id: `alert_${Date.now()}`,
        child_id: newChild.id,
        child_name: newChild.name,
        type: 'inappropriate_interaction',
        severity: 'medium',
        message: `تم إنشاء ملف تعريف للطفل ${newChild.name} بنجاح`,
        details: 'تم إنشاء ملف تعريف جديد بنجاح مع إعدادات الأمان الافتراضية',
        timestamp: new Date().toISOString(),
        resolved: false,
        risk_score: 10,
        auto_resolved: false,
        requires_immediate_action: false,
        escalation_level: 1,
        context: {
          previous_warnings: 0
        }
      });

      console.log('✅ Child profile created successfully:', newChild.id);
      return newChild;

    } catch (error) {
      console.error('❌ Error creating child profile:', error);
      throw error;
    }
  }

  /**
   * الحصول على جميع ملفات الأطفال
   */
  public async getAllChildProfiles(): Promise<ChildProfile[]> {
    try {
      await this.loadStoredProfiles();
      
      return Array.from(this.childProfiles.values())
        .filter(child => child.is_active)
        .sort((a, b) => new Date(b.last_accessed).getTime() - new Date(a.last_accessed).getTime());

    } catch (error) {
      console.error('❌ Error getting child profiles:', error);
      return [];
    }
  }

  /**
   * الحصول على ملف تعريف طفل محدد
   */
  public async getChildProfile(childId: string): Promise<ChildProfile | null> {
    try {
      // البحث في الذاكرة أولاً
      if (this.childProfiles.has(childId)) {
        return this.childProfiles.get(childId) || null;
      }

      // البحث في التخزين المحلي
      const stored = await AsyncStorage.getItem(`child_profile_${childId}`);
      if (stored) {
        const profile = JSON.parse(stored);
        this.childProfiles.set(childId, profile);
        return profile;
      }

      // محاولة الحصول من الخادم
      const apiChild = await ApiService.getChild(childId);
      if (apiChild) {
        // تحويل ApiChild إلى ChildProfile مع القيم الافتراضية
        const profile: ChildProfile = {
          id: apiChild.id,
          name: apiChild.name,
          age: apiChild.age,
          date_of_birth: '',
          privacy_settings: this.getDefaultPrivacySettings(),
          emergency_contacts: [],
          parent_permissions: this.getDefaultParentPermissions(),
          safety_preferences: this.getDefaultSafetyPreferences(),
          created_at: apiChild.created_at,
          last_accessed: new Date().toISOString(),
          is_active: true
        };
        await this.saveChildProfile(profile);
        return profile;
      }

      return null;

    } catch (error) {
      console.error('❌ Error getting child profile:', error);
      return null;
    }
  }

  /**
   * تحديث ملف تعريف الطفل
   */
  public async updateChildProfile(
    childId: string, 
    updates: Partial<ChildProfile>
  ): Promise<ChildProfile | null> {
    try {
      console.log('📝 Updating child profile:', childId);

      const currentProfile = await this.getChildProfile(childId);
      if (!currentProfile) {
        throw new Error('Child profile not found');
      }

      // التحقق من صلاحيات التعديل
      if (!this.canModifyProfile(childId)) {
        throw new Error('Insufficient permissions to modify profile');
      }

      // دمج التحديثات
      const updatedProfile: ChildProfile = {
        ...currentProfile,
        ...updates,
        last_accessed: new Date().toISOString()
      };

      // التحقق من صحة البيانات المحدثة
      this.validateChildData(updatedProfile);

      // حفظ التحديثات
      await this.saveChildProfile(updatedProfile);

      // إشعار بالتحديث
      this.emit('child_profile_updated', { childId, updates });

      console.log('✅ Child profile updated successfully');
      return updatedProfile;

    } catch (error) {
      console.error('❌ Error updating child profile:', error);
      throw error;
    }
  }

  /**
   * تبديل الطفل النشط
   */
  public async switchActiveChild(childId: string, pin?: string): Promise<boolean> {
    try {
      console.log('🔄 Switching to child:', childId);

      const childProfile = await this.getChildProfile(childId);
      if (!childProfile) {
        throw new Error('Child profile not found');
      }

      // التحقق من صلاحيات الوصول
      if (childProfile.parent_permissions.requires_pin_for_access) {
        if (!pin) {
          throw new Error('PIN required for access');
        }

        const isValidPin = await this.validatePin(childId, pin);
        if (!isValidPin) {
          throw new Error('Invalid PIN');
        }
      }

      // إنهاء الجلسة الحالية
      if (this.currentSession) {
        await this.endCurrentSession();
      }

      // بدء جلسة جديدة
      const session = await this.startChildSession(childId);

      // تحديث الطفل النشط
      this.activeChildId = childId;
      this.currentSession = session;

      // تحديث وقت الوصول
      await this.updateLastAccessed(childId);

      // إعداد مؤقت انتهاء الجلسة
      this.setupSessionTimeout(childProfile.parent_permissions.session_timeout_minutes);

      // إشعار بالتبديل
      this.emit('active_child_changed', { childId, session });

      console.log('✅ Successfully switched to child:', childId);
      return true;

    } catch (error) {
      console.error('❌ Error switching active child:', error);
      throw error;
    }
  }

  /**
   * الحصول على الطفل النشط حالياً
   */
  public getActiveChild(): ChildProfile | null {
    if (!this.activeChildId) {
      return null;
    }

    return this.childProfiles.get(this.activeChildId) || null;
  }

  /**
   * التحقق من الجلسة النشطة
   */
  public isSessionActive(): boolean {
    if (!this.currentSession) {
      return false;
    }

    const now = new Date();
    const timeout = new Date(this.currentSession.session_timeout);

    return now < timeout && this.currentSession.authenticated;
  }

  /**
   * تحديث إعدادات الخصوصية
   */
  public async updatePrivacySettings(
    childId: string, 
    settings: Partial<ChildPrivacySettings>
  ): Promise<boolean> {
    try {
      console.log('🔒 Updating privacy settings for child:', childId);

      const profile = await this.getChildProfile(childId);
      if (!profile) {
        throw new Error('Child profile not found');
      }

      const updatedSettings = {
        ...profile.privacy_settings,
        ...settings
      };

      await this.updateChildProfile(childId, {
        privacy_settings: updatedSettings
      });

      // إشعار بتحديث الخصوصية
      this.emit('privacy_settings_updated', { childId, settings: updatedSettings });

      // إنشاء تنبيه للمراجعة
      if (settings.data_sharing === false || settings.analytics_enabled === false) {
        this.alertService.addNewAlert({
          id: `alert_${Date.now()}`,
          child_id: childId,
          child_name: profile.name,
          type: 'inappropriate_interaction',
          severity: 'medium',
          message: `تم تحديث إعدادات الخصوصية للطفل ${profile.name}`,
          details: 'تم تحديث إعدادات الخصوصية',
          timestamp: new Date().toISOString(),
          resolved: false,
          risk_score: 10,
          auto_resolved: false,
          requires_immediate_action: false,
          escalation_level: 1
        });
      }

      console.log('✅ Privacy settings updated successfully');
      return true;

    } catch (error) {
      console.error('❌ Error updating privacy settings:', error);
      throw error;
    }
  }

  /**
   * تحديث تفضيلات الأمان
   */
  public async updateSafetyPreferences(
    childId: string, 
    preferences: Partial<SafetyPreferences>
  ): Promise<boolean> {
    try {
      console.log('🛡️ Updating safety preferences for child:', childId);

      const profile = await this.getChildProfile(childId);
      if (!profile) {
        throw new Error('Child profile not found');
      }

      const updatedPreferences = {
        ...profile.safety_preferences,
        ...preferences
      };

      await this.updateChildProfile(childId, {
        safety_preferences: updatedPreferences
      });

      // إشعار بتحديث الأمان
      this.emit('safety_preferences_updated', { childId, preferences: updatedPreferences });

      // إنشاء تنبيه إذا تم تقليل مستوى الأمان
      const currentLevel = profile.safety_preferences.content_filter_level;
      const newLevel = preferences.content_filter_level;

      if (newLevel && this.isSecurityDowngrade(currentLevel, newLevel)) {
        this.alertService.addNewAlert({
          id: `alert_${Date.now()}`,
          child_id: childId,
          child_name: profile.name,
          type: 'inappropriate_interaction',
          severity: 'high',
          message: `تم تقليل مستوى الأمان للطفل ${profile.name} من ${currentLevel} إلى ${newLevel}`,
          details: 'تم تقليل مستوى فلترة المحتوى',
          timestamp: new Date().toISOString(),
          resolved: false,
          risk_score: 30,
          auto_resolved: false,
          requires_immediate_action: false,
          escalation_level: 2
        });
      }

      console.log('✅ Safety preferences updated successfully');
      return true;

    } catch (error) {
      console.error('❌ Error updating safety preferences:', error);
      throw error;
    }
  }

  /**
   * إضافة جهة اتصال طوارئ
   */
  public async addEmergencyContact(
    childId: string, 
    contact: Omit<EmergencyContact, 'id'>
  ): Promise<boolean> {
    try {
      console.log('📞 Adding emergency contact for child:', childId);

      const profile = await this.getChildProfile(childId);
      if (!profile) {
        throw new Error('Child profile not found');
      }

      const newContact: EmergencyContact = {
        ...contact,
        id: `contact_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      };

      const updatedContacts = [...profile.emergency_contacts, newContact];

      await this.updateChildProfile(childId, {
        emergency_contacts: updatedContacts
      });

      // إشعار بإضافة جهة الاتصال
      this.emit('emergency_contact_added', { childId, contact: newContact });

      console.log('✅ Emergency contact added successfully');
      return true;

    } catch (error) {
      console.error('❌ Error adding emergency contact:', error);
      throw error;
    }
  }

  /**
   * حذف ملف تعريف الطفل (إلغاء تفعيل)
   */
  public async deleteChildProfile(childId: string, permanent: boolean = false): Promise<boolean> {
    try {
      console.log(`🗑️ ${permanent ? 'Permanently deleting' : 'Deactivating'} child profile:`, childId);

      const profile = await this.getChildProfile(childId);
      if (!profile) {
        throw new Error('Child profile not found');
      }

      if (permanent) {
        // حذف نهائي
        this.childProfiles.delete(childId);
        await AsyncStorage.removeItem(`child_profile_${childId}`);
        
        // حذف من الخادم (محاكاة - سيتم تنفيذها لاحقاً)
        console.log('🗑️ Would delete child from server:', childId);
      } else {
        // إلغاء تفعيل فقط
        await this.updateChildProfile(childId, { is_active: false });
      }

      // إنهاء الجلسة إذا كان هذا الطفل نشط
      if (this.activeChildId === childId) {
        await this.endCurrentSession();
      }

      // إشعار بالحذف
      this.emit('child_profile_deleted', { childId, permanent });

      console.log('✅ Child profile deleted successfully');
      return true;

    } catch (error) {
      console.error('❌ Error deleting child profile:', error);
      throw error;
    }
  }

  /**
   * استعادة نسخة احتياطية من بيانات الطفل
   */
  public async restoreChildData(childId: string, backupData: any): Promise<boolean> {
    try {
      console.log('🔄 Restoring child data from backup:', childId);

      // التحقق من صحة البيانات المستعادة
      this.validateBackupData(backupData);

      // استعادة الملف التعريفي
      const restoredProfile: ChildProfile = {
        ...backupData.profile,
        last_accessed: new Date().toISOString()
      };

      await this.saveChildProfile(restoredProfile);

      // إشعار بالاستعادة
      this.emit('child_data_restored', { childId, backupDate: backupData.created_at });

      console.log('✅ Child data restored successfully');
      return true;

    } catch (error) {
      console.error('❌ Error restoring child data:', error);
      throw error;
    }
  }

  /**
   * دوال مساعدة خاصة
   */
  private validateChildData(childData: Partial<ChildProfile>): void {
    if (!childData.name || childData.name.trim().length === 0) {
      throw new Error('Child name is required');
    }

    if (childData.age && (childData.age < 3 || childData.age > 13)) {
      throw new Error('Child age must be between 3 and 13 for COPPA compliance');
    }

    if (childData.date_of_birth) {
      const birthDate = new Date(childData.date_of_birth);
      const age = this.calculateAge(birthDate);
      if (age < 3 || age > 13) {
        throw new Error('Child age calculated from birth date must be between 3 and 13');
      }
    }
  }

  private calculateAge(birthDate: Date): number {
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();
    
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
      age--;
    }
    
    return age;
  }

  private getDefaultPrivacySettings(): ChildPrivacySettings {
    return {
      data_sharing: false,
      analytics_enabled: true,
      interaction_logging: true,
      external_communication: false,
      location_access: false,
      camera_access: false,
      microphone_access: false,
      report_sharing: true
    };
  }

  private getDefaultParentPermissions(): ParentPermissions {
    return {
      can_view_interactions: true,
      can_modify_settings: true,
      can_delete_data: true,
      can_share_reports: true,
      requires_pin_for_access: false,
      session_timeout_minutes: 30,
      two_factor_enabled: false
    };
  }

  private getDefaultSafetyPreferences(): SafetyPreferences {
    return {
      content_filter_level: 'high',
      time_restrictions: [],
      allowed_topics: ['education', 'games', 'stories', 'science'],
      blocked_topics: ['violence', 'adult_content', 'politics'],
      emergency_keywords: ['help', 'scared', 'hurt', 'emergency'],
      auto_alert_enabled: true,
      parent_notification_level: 'all'
    };
  }

  private async saveChildProfile(profile: ChildProfile): Promise<void> {
    try {
      // حفظ في الذاكرة
      this.childProfiles.set(profile.id, profile);

      // حفظ محلياً
      await AsyncStorage.setItem(`child_profile_${profile.id}`, JSON.stringify(profile));

      // مزامنة مع الخادم (محاكاة - سيتم تنفيذها لاحقاً)
      console.log('🔄 Would sync child profile to server:', profile.id);

      console.log('✅ Child profile saved successfully:', profile.id);
    } catch (error) {
      console.error('❌ Error saving child profile:', error);
      throw error;
    }
  }

  private async loadStoredProfiles(): Promise<void> {
    try {
      const keys = await AsyncStorage.getAllKeys();
      const profileKeys = keys.filter(key => key.startsWith('child_profile_'));

      for (const key of profileKeys) {
        const profileData = await AsyncStorage.getItem(key);
        if (profileData) {
          const profile = JSON.parse(profileData);
          this.childProfiles.set(profile.id, profile);
        }
      }

      console.log(`✅ Loaded ${profileKeys.length} child profiles from storage`);
    } catch (error) {
      console.error('❌ Error loading stored profiles:', error);
    }
  }

  private canModifyProfile(childId: string): boolean {
    const profile = this.childProfiles.get(childId);
    if (!profile) return false;

    return profile.parent_permissions.can_modify_settings;
  }

  private async validatePin(childId: string, pin: string): Promise<boolean> {
    try {
      const profile = this.childProfiles.get(childId);
      if (!profile || !profile.parent_permissions.pin_hash) {
        return false;
      }

      // في التطبيق الحقيقي سيتم استخدام bcrypt أو مشابه
      const hashedPin = this.hashPin(pin);
      return hashedPin === profile.parent_permissions.pin_hash;
    } catch (error) {
      console.error('❌ Error validating PIN:', error);
      return false;
    }
  }

  private hashPin(pin: string): string {
    // محاكاة تشفير PIN (في التطبيق الحقيقي استخدم bcrypt)
    return Buffer.from(pin).toString('base64');
  }

  private async startChildSession(childId: string): Promise<ChildSession> {
    const profile = this.childProfiles.get(childId);
    if (!profile) {
      throw new Error('Child profile not found');
    }

    const timeoutMinutes = profile.parent_permissions.session_timeout_minutes;
    const sessionTimeout = new Date();
    sessionTimeout.setMinutes(sessionTimeout.getMinutes() + timeoutMinutes);

    const session: ChildSession = {
      child_id: childId,
      session_start: new Date().toISOString(),
      session_timeout: sessionTimeout.toISOString(),
      authenticated: true,
      permissions_granted: this.getSessionPermissions(profile)
    };

    // حفظ الجلسة
    await AsyncStorage.setItem('current_child_session', JSON.stringify(session));

    return session;
  }

  private getSessionPermissions(profile: ChildProfile): string[] {
    const permissions: string[] = [];

    if (profile.parent_permissions.can_view_interactions) {
      permissions.push('view_interactions');
    }

    if (profile.parent_permissions.can_modify_settings) {
      permissions.push('modify_settings');
    }

    if (profile.parent_permissions.can_share_reports) {
      permissions.push('share_reports');
    }

    return permissions;
  }

  private async endCurrentSession(): Promise<void> {
    if (this.currentSession) {
      this.emit('session_ended', this.currentSession);
      this.currentSession = null;
      this.activeChildId = null;

      if (this.sessionTimer) {
        clearTimeout(this.sessionTimer);
        this.sessionTimer = null;
      }

      await AsyncStorage.removeItem('current_child_session');
      console.log('✅ Child session ended');
    }
  }

  private setupSessionTimeout(timeoutMinutes: number): void {
    if (this.sessionTimer) {
      clearTimeout(this.sessionTimer);
    }

    this.sessionTimer = setTimeout(async () => {
      console.log('⏰ Session timeout reached');
      await this.endCurrentSession();
      this.emit('session_timeout');
    }, timeoutMinutes * 60 * 1000);
  }

  private async updateLastAccessed(childId: string): Promise<void> {
    const profile = this.childProfiles.get(childId);
    if (profile) {
      profile.last_accessed = new Date().toISOString();
      await this.saveChildProfile(profile);
    }
  }

  private isSecurityDowngrade(
    currentLevel: 'low' | 'medium' | 'high' | 'maximum',
    newLevel: 'low' | 'medium' | 'high' | 'maximum'
  ): boolean {
    const levels = { low: 1, medium: 2, high: 3, maximum: 4 };
    return levels[newLevel] < levels[currentLevel];
  }

  private validateBackupData(backupData: any): void {
    if (!backupData || !backupData.profile) {
      throw new Error('Invalid backup data structure');
    }

    if (!backupData.profile.id || !backupData.profile.name) {
      throw new Error('Backup data missing essential profile information');
    }

    // إضافة المزيد من التحققات حسب الحاجة
  }

  /**
   * تنظيف الموارد
   */
  public async cleanup(): Promise<void> {
    if (this.sessionTimer) {
      clearTimeout(this.sessionTimer);
    }

    await this.endCurrentSession();
    this.childProfiles.clear();
    this.removeAllListeners();
    
    console.log('✅ MultiChildManager cleanup completed');
  }
}

export default MultiChildManager;
