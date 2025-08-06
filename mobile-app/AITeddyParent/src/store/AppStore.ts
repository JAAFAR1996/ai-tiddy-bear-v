/**
 * Centralized State Management - إدارة الحالة المركزية
 * 
 * Using Zustand for lightweight, TypeScript-friendly state management
 * 
 * Features:
 * - Authentication state
 * - User and children data  
 * - App settings and preferences
 * - Network status
 * - Push notifications state
 * - Loading states
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Child, User, SafetyAlert, Interaction } from '../types';

// Authentication State
interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  lastLoginTime: string | null;
  
  // Actions
  setAuthenticated: (authenticated: boolean) => void;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

// Children & Family State
interface FamilyState {
  children: Child[];
  selectedChildId: string | null;
  interactions: Interaction[];
  safetyAlerts: SafetyAlert[];
  
  // Loading states
  childrenLoading: boolean;
  interactionsLoading: boolean;
  alertsLoading: boolean;
  
  // Actions
  setChildren: (children: Child[]) => void;
  addChild: (child: Child) => void;
  updateChild: (childId: string, updates: Partial<Child>) => void;
  removeChild: (childId: string) => void;
  selectChild: (childId: string | null) => void;
  
  setInteractions: (interactions: Interaction[]) => void;
  addInteraction: (interaction: Interaction) => void;
  
  setSafetyAlerts: (alerts: SafetyAlert[]) => void;
  addSafetyAlert: (alert: SafetyAlert) => void;
  markAlertAsResolved: (alertId: string) => void;
  
  // Loading actions
  setChildrenLoading: (loading: boolean) => void;
  setInteractionsLoading: (loading: boolean) => void;
  setAlertsLoading: (loading: boolean) => void;
}

// App Settings & Preferences
interface SettingsState {
  // UI Preferences
  language: 'ar' | 'en';
  theme: 'light' | 'dark' | 'system';
  fontSize: 'small' | 'medium' | 'large';
  
  // Notification Settings
  pushNotificationsEnabled: boolean;
  safetyAlertsEnabled: boolean;
  childUpdatesEnabled: boolean;
  systemNotificationsEnabled: boolean;
  soundEnabled: boolean;
  vibrationEnabled: boolean;
  
  // Safety Settings
  contentFilterLevel: 'strict' | 'moderate' | 'relaxed';
  maxDailyUsage: number; // minutes
  bedtimeMode: boolean;
  bedtimeStart: string; // HH:MM
  bedtimeEnd: string; // HH:MM
  
  // Actions
  setLanguage: (language: 'ar' | 'en') => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  setFontSize: (size: 'small' | 'medium' | 'large') => void;
  
  updateNotificationSettings: (settings: Partial<{
    pushNotificationsEnabled: boolean;
    safetyAlertsEnabled: boolean;
    childUpdatesEnabled: boolean;
    systemNotificationsEnabled: boolean;
    soundEnabled: boolean;
    vibrationEnabled: boolean;
  }>) => void;
  
  updateSafetySettings: (settings: Partial<{
    contentFilterLevel: 'strict' | 'moderate' | 'relaxed';
    maxDailyUsage: number;
    bedtimeMode: boolean;
    bedtimeStart: string;
    bedtimeEnd: string;
  }>) => void;
}

// Network & System State
interface SystemState {
  // Network status
  isOnline: boolean;
  connectionType: 'wifi' | 'cellular' | 'none' | 'unknown';
  
  // App status
  isInBackground: boolean;
  lastActiveTime: string | null;
  
  // Push notifications
  pushToken: string | null;
  pushPermissionGranted: boolean;
  
  // Error handling
  lastError: string | null;
  errorCount: number;
  
  // Actions
  setNetworkStatus: (online: boolean, type: 'wifi' | 'cellular' | 'none' | 'unknown') => void;
  setAppState: (inBackground: boolean) => void;
  setPushToken: (token: string | null) => void;
  setPushPermission: (granted: boolean) => void;
  setError: (error: string | null) => void;
  clearErrors: () => void;
}

// Create Auth Store
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      isAuthenticated: false,
      isLoading: false,
      user: null,
      lastLoginTime: null,
      
      setAuthenticated: (authenticated) => 
        set({ 
          isAuthenticated: authenticated,
          lastLoginTime: authenticated ? new Date().toISOString() : null 
        }),
      
      setUser: (user) => set({ user }),
      
      setLoading: (loading) => set({ isLoading: loading }),
      
      logout: () => set({ 
        isAuthenticated: false, 
        user: null, 
        lastLoginTime: null 
      }),
    }),
    {
      name: 'auth-store',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        user: state.user,
        lastLoginTime: state.lastLoginTime,
      }),
    }
  )
);

// Create Family Store
export const useFamilyStore = create<FamilyState>()((set, get) => ({
  children: [],
  selectedChildId: null,
  interactions: [],
  safetyAlerts: [],
  
  childrenLoading: false,
  interactionsLoading: false,
  alertsLoading: false,
  
  setChildren: (children) => set({ children }),
  
  addChild: (child) => set((state) => ({
    children: [...state.children, child]
  })),
  
  updateChild: (childId, updates) => set((state) => ({
    children: state.children.map(child => 
      child.id === childId ? { ...child, ...updates } : child
    )
  })),
  
  removeChild: (childId) => set((state) => ({
    children: state.children.filter(child => child.id !== childId),
    selectedChildId: state.selectedChildId === childId ? null : state.selectedChildId
  })),
  
  selectChild: (childId) => set({ selectedChildId: childId }),
  
  setInteractions: (interactions) => set({ interactions }),
  
  addInteraction: (interaction) => set((state) => ({
    interactions: [interaction, ...state.interactions].slice(0, 50) // Keep last 50
  })),
  
  setSafetyAlerts: (alerts) => set({ safetyAlerts: alerts }),
  
  addSafetyAlert: (alert) => set((state) => ({
    safetyAlerts: [alert, ...state.safetyAlerts]
  })),
  
  markAlertAsResolved: (alertId) => set((state) => ({
    safetyAlerts: state.safetyAlerts.map(alert =>
      alert.id === alertId ? { ...alert, resolved: true } : alert
    )
  })),
  
  setChildrenLoading: (loading) => set({ childrenLoading: loading }),
  setInteractionsLoading: (loading) => set({ interactionsLoading: loading }),
  setAlertsLoading: (loading) => set({ alertsLoading: loading }),
}));

// Create Settings Store
export const useSettingsStore = create<SettingsState>()(
  persist(
    (set, get) => ({
      // UI Preferences - default to Arabic/RTL
      language: 'ar',
      theme: 'light',
      fontSize: 'medium',
      
      // Notification Settings - safety-first defaults
      pushNotificationsEnabled: true,
      safetyAlertsEnabled: true,
      childUpdatesEnabled: true,
      systemNotificationsEnabled: false,
      soundEnabled: true,
      vibrationEnabled: true,
      
      // Safety Settings - strict defaults for child protection
      contentFilterLevel: 'strict',
      maxDailyUsage: 120, // 2 hours
      bedtimeMode: true,
      bedtimeStart: '20:00',
      bedtimeEnd: '07:00',
      
      setLanguage: (language) => set({ language }),
      setTheme: (theme) => set({ theme }),
      setFontSize: (fontSize) => set({ fontSize }),
      
      updateNotificationSettings: (settings) => set((state) => ({
        ...state,
        ...settings
      })),
      
      updateSafetySettings: (settings) => set((state) => ({
        ...state,
        ...settings
      })),
    }),
    {
      name: 'settings-store',
      storage: createJSONStorage(() => AsyncStorage),
    }
  )
);

// Create System Store
export const useSystemStore = create<SystemState>()((set, get) => ({
  isOnline: true,
  connectionType: 'unknown',
  isInBackground: false,
  lastActiveTime: null,
  pushToken: null,
  pushPermissionGranted: false,
  lastError: null,
  errorCount: 0,
  
  setNetworkStatus: (online, type) => set({ 
    isOnline: online, 
    connectionType: type 
  }),
  
  setAppState: (inBackground) => set({ 
    isInBackground: inBackground,
    lastActiveTime: inBackground ? new Date().toISOString() : null
  }),
  
  setPushToken: (token) => set({ pushToken: token }),
  
  setPushPermission: (granted) => set({ pushPermissionGranted: granted }),
  
  setError: (error) => set((state) => ({ 
    lastError: error,
    errorCount: error ? state.errorCount + 1 : state.errorCount
  })),
  
  clearErrors: () => set({ lastError: null, errorCount: 0 }),
}));

// Composite selectors for common use cases
export const useAppState = () => {
  const authState = useAuthStore();
  const familyState = useFamilyStore();
  const settingsState = useSettingsStore();
  const systemState = useSystemStore();
  
  return {
    // Combined loading state
    isLoading: authState.isLoading || 
               familyState.childrenLoading || 
               familyState.interactionsLoading || 
               familyState.alertsLoading,
    
    // Safety status
    hasUnresolvedAlerts: familyState.safetyAlerts.some(alert => !alert.resolved),
    alertCount: familyState.safetyAlerts.filter(alert => !alert.resolved).length,
    
    // Selected child info
    selectedChild: familyState.children.find(child => 
      child.id === familyState.selectedChildId
    ),
    
    // System health
    isHealthy: systemState.isOnline && 
               systemState.errorCount < 5 &&
               !systemState.lastError,
    
    // Notification readiness
    canReceiveNotifications: systemState.pushPermissionGranted && 
                           systemState.pushToken !== null &&
                           settingsState.pushNotificationsEnabled,
  };
};

// Action helpers
export const useAppActions = () => {
  const authActions = useAuthStore();
  const familyActions = useFamilyStore();
  const settingsActions = useSettingsStore();
  const systemActions = useSystemStore();
  
  return {
    // Combined logout
    logout: () => {
      authActions.logout();
      familyActions.setChildren([]);
      familyActions.setInteractions([]);
      familyActions.setSafetyAlerts([]);
      systemActions.clearErrors();
    },
    
    // Emergency alert handler
    handleEmergencyAlert: (alert: SafetyAlert) => {
      familyActions.addSafetyAlert(alert);
      // Could trigger additional emergency actions here
    },
    
    // Network status update
    updateNetworkStatus: (online: boolean, type: 'wifi' | 'cellular' | 'none' | 'unknown') => {
      systemActions.setNetworkStatus(online, type);
      if (!online) {
        systemActions.setError('اتصال الشبكة منقطع');
      } else {
        systemActions.clearErrors();
      }
    },
  };
};

export default {
  useAuthStore,
  useFamilyStore,
  useSettingsStore,
  useSystemStore,
  useAppState,
  useAppActions,
};