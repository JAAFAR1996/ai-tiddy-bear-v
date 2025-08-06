/**
 * Type definitions for AI Teddy Parent App
 * Comprehensive type system for all services and components
 * 
 * @version 2.0.0
 * @since 2025-08-04
 */

// =============================================================================
// API TYPES
// =============================================================================

export interface User {
  id: string;
  email: string;
  name: string;
}

export interface ApiChild {
  id: string;
  name: string;
  age: number;
  created_at: string;
}

export interface Child extends ApiChild {
  last_interaction: string;
  preferences: any;
}

export interface ApiInteraction {
  id: string;
  child_id: string;
  child_name?: string;
  conversation_id?: string;
  user_message: string;
  ai_response: string;
  timestamp: string;
  has_forbidden_content: boolean;
  duration_seconds?: number;
  usage_duration?: number;
}

export interface Interaction extends ApiInteraction {
  question: string;
  response: string;
}

export interface ApiSafetyAlert {
  id: string;
  child_id: string;
  child_name?: string;
  type: string;
  severity: string;
  message: string;
  details?: string;
  timestamp: string;
  resolved?: boolean;
  resolved_at?: string;
  resolved_by?: string;
  risk_score?: number;
  auto_resolved?: boolean;
  requires_immediate_action?: boolean;
  escalation_level?: number;
  context?: any;
}

export interface SafetyAlert {
  id: string;
  child_id: string;
  child_name: string;
  alert_type?: 'forbidden_content' | 'usage_limit' | 'safety_concern';
  type: 'forbidden_content' | 'self_harm' | 'excessive_usage' | 'inappropriate_interaction' | 'emergency';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  details: string;
  timestamp: string;
  resolved: boolean;
  resolved_at?: string;
  resolved_by?: string;
  risk_score: number;
  auto_resolved: boolean;
  requires_immediate_action: boolean;
  escalation_level: number;
  context?: {
    conversation_id?: string;
    message_content?: string;
    interaction_duration?: number;
    previous_warnings?: number;
  };
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface DashboardData {
  children: Child[];
  totalInteractions: number;
  activeAlerts: SafetyAlert[];
  lastUpdate: string;
}

// =============================================================================
// ALERT SYSTEM TYPES
// =============================================================================

export interface AlertSummary {
  total_alerts: number;
  unresolved_alerts: number;
  critical_alerts: number;
  high_priority_alerts: number;
  alerts_today: number;
  alerts_this_week: number;
  most_common_type: string;
  average_resolution_time_hours: number;
  escalation_rate: number;
}

export interface RiskAssessment {
  child_id: string;
  overall_risk_score: number;
  risk_factors: RiskFactor[];
  recommendations: string[];
  last_updated: string;
  trend: 'improving' | 'stable' | 'deteriorating';
}

export interface RiskFactor {
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  weight: number;
  recent_incidents: number;
}

export interface EscalationRule {
  id: string;
  condition: string;
  action: string;
  delay_minutes: number;
  active: boolean;
}

// =============================================================================
// NOTIFICATION TYPES
// =============================================================================

export interface PushNotification {
  id: string;
  title: string;
  body: string;
  data?: any;
  priority: 'low' | 'normal' | 'high';
  scheduled_time?: string;
  child_id?: string;
  alert_id?: string;
}

export interface NotificationSettings {
  push_enabled: boolean;
  email_enabled: boolean;
  sms_enabled: boolean;
  severity_threshold: 'low' | 'medium' | 'high' | 'critical';
  quiet_hours_start?: string;
  quiet_hours_end?: string;
  emergency_bypass: boolean;
}

// =============================================================================
// REPORTS TYPES
// =============================================================================

export interface ReportMetrics {
  daily: DailyMetric[];
  weekly: WeeklyMetric[];
  monthly: MonthlyMetric[];
  trends: TrendAnalysis;
  insights: BehaviorInsight[];
}

export interface DailyMetric {
  date: string;
  total_interactions: number;
  total_duration: number;
  safety_incidents: number;
  mood_score: number;
  favorite_topics: string[];
}

export interface WeeklyMetric {
  week_start: string;
  week_end: string;
  total_interactions: number;
  avg_daily_usage: number;
  safety_score: number;
  learning_progress: number;
  social_development: number;
}

export interface MonthlyMetric {
  month: string;
  year: number;
  total_interactions: number;
  growth_milestones: string[];
  concern_areas: string[];
  recommendations: string[];
}

export interface TrendAnalysis {
  usage_trend: 'increasing' | 'stable' | 'decreasing';
  safety_trend: 'improving' | 'stable' | 'concerning';
  engagement_trend: 'high' | 'medium' | 'low';
  development_areas: string[];
}

export interface BehaviorInsight {
  category: string;
  description: string;
  impact: 'positive' | 'neutral' | 'concerning';
  confidence: number;
  recommendations: string[];
}

export interface ReportExportOptions {
  format: 'pdf' | 'csv' | 'json';
  period: 'daily' | 'weekly' | 'monthly';
  child_ids: string[];
  include_insights: boolean;
  include_recommendations: boolean;
}

// =============================================================================
// MULTI-CHILD MANAGEMENT TYPES
// =============================================================================

export interface ChildProfile {
  id: string;
  name: string;
  age: number;
  avatar_url?: string;
  created_at: string;
  last_active: string;
  is_active: boolean;
  parent_id: string;
  
  // Safety Settings
  safety_settings: ChildSafetySettings;
  
  // Usage Settings
  usage_limits: UsageLimits;
  
  // Emergency Contacts
  emergency_contacts: EmergencyContact[];
  
  // Session Info
  current_session?: ChildSession;
  
  // Statistics
  total_interactions: number;
  total_usage_time: number;
  safety_score: number;
}

export interface ChildSafetySettings {
  content_filter_level: 'strict' | 'moderate' | 'basic';
  blocked_topics: string[];
  allowed_topics: string[];
  auto_escalate_enabled: boolean;
  parental_review_required: boolean;
  safe_words: string[];
  risk_tolerance: 'low' | 'medium' | 'high';
}

export interface UsageLimits {
  daily_minutes: number;
  weekly_minutes: number;
  session_max_minutes: number;
  break_intervals: number;
  bedtime_restrictions: {
    enabled: boolean;
    start_time: string;
    end_time: string;
  };
  weekend_different_limits: boolean;
  weekend_daily_minutes?: number;
}

export interface EmergencyContact {
  id: string;
  name: string;
  relationship: string;
  phone: string;
  email?: string;
  priority: number;
  notify_immediately: boolean;
}

export interface ChildSession {
  id: string;
  child_id: string;
  start_time: string;
  last_activity: string;
  duration_minutes: number;
  interactions_count: number;
  is_active: boolean;
  device_info?: {
    platform: string;
    app_version: string;
    location?: string;
  };
}

export interface MultiChildSummary {
  total_children: number;
  active_children: number;
  total_alerts: number;
  unresolved_alerts: number;
  usage_summary: {
    total_minutes_today: number;
    total_interactions_today: number;
    most_active_child: string;
  };
}

// =============================================================================
// SUBSCRIPTION TYPES
// =============================================================================

export interface SubscriptionTier {
  id: string;
  name: string;
  name_ar: string;
  price_monthly_iqd: number;
  price_yearly_iqd: number;
  features: SubscriptionFeature[];
  limits: SubscriptionLimits;
  is_popular: boolean;
  trial_days: number;
}

export interface SubscriptionFeature {
  id: string;
  name: string;
  name_ar: string;
  description: string;
  description_ar: string;
  included: boolean;
}

export interface SubscriptionLimits {
  max_children: number;
  max_monthly_interactions: number;
  max_reports_per_month: number;
  advanced_analytics: boolean;
  priority_support: boolean;
  custom_alerts: boolean;
  data_export: boolean;
}

export interface UserSubscription {
  id: string;
  user_id: string;
  tier_id: string;
  tier_name: string;
  status: 'active' | 'cancelled' | 'expired' | 'trial';
  start_date: string;
  end_date: string;
  auto_renew: boolean;
  payment_method: PaymentMethod;
  trial_end_date?: string;
  
  // Usage tracking
  current_usage: SubscriptionUsage;
  
  // Billing
  last_payment_date?: string;
  next_billing_date?: string;
  billing_history: BillingRecord[];
}

export interface PaymentMethod {
  type: 'zaincash' | 'asiacell' | 'credit_card' | 'bank_transfer';
  display_name: string;
  last_four?: string;
  expires_at?: string;
  is_default: boolean;
}

export interface SubscriptionUsage {
  children_count: number;
  monthly_interactions: number;
  reports_generated: number;
  data_exports: number;
  reset_date: string;
}

export interface BillingRecord {
  id: string;
  amount_iqd: number;
  currency: 'IQD';
  description: string;
  payment_date: string;
  payment_method: string;
  status: 'paid' | 'pending' | 'failed' | 'refunded';
  invoice_url?: string;
}

export interface PaymentRequest {
  tier_id: string;
  billing_cycle: 'monthly' | 'yearly';
  payment_method_type: 'zaincash' | 'asiacell' | 'credit_card';
  phone_number?: string;
  return_url?: string;
}

// =============================================================================
// INTERACTION MANAGEMENT TYPES
// =============================================================================

export interface InteractionMetadata {
  conversation_id: string;
  session_id: string;
  device_info: string;
  location?: string;
  app_version: string;
  response_time_ms: number;
  user_satisfaction?: number;
  flagged_content: boolean;
  auto_responses_used: number;
}

export interface ContentAnalysis {
  safety_score: number;
  sentiment_score: number;
  topics_detected: string[];
  language_detected: string;
  complexity_level: 'simple' | 'moderate' | 'complex';
  educational_value: number;
  flags: ContentFlag[];
}

export interface ContentFlag {
  type: 'inappropriate' | 'violence' | 'personal_info' | 'emotional_distress' | 'other';
  severity: 'low' | 'medium' | 'high';
  description: string;
  confidence: number;
  auto_handled: boolean;
}

export interface ConversationSummary {
  id: string;
  child_id: string;
  start_time: string;
  end_time: string;
  total_interactions: number;
  dominant_topics: string[];
  overall_sentiment: 'positive' | 'neutral' | 'negative';
  safety_incidents: number;
  key_insights: string[];
  follow_up_needed: boolean;
}

export interface InteractionFilter {
  child_ids?: string[];
  date_from?: string;
  date_to?: string;
  content_flags?: string[];
  sentiment?: string[];
  topics?: string[];
  safety_score_min?: number;
  has_concerns?: boolean;
  limit?: number;
  offset?: number;
}

export interface BulkInteractionOperation {
  operation: 'delete' | 'flag' | 'export' | 'analyze';
  interaction_ids: string[];
  options?: {
    flag_type?: string;
    export_format?: 'csv' | 'json' | 'pdf';
    analysis_type?: 'sentiment' | 'topics' | 'safety';
  };
}

// =============================================================================
// UI COMPONENT TYPES
// =============================================================================

export interface AlertModalProps {
  visible: boolean;
  alert: SafetyAlert | null;
  onClose: () => void;
  onResolve: (alertId: string, notes?: string) => void;
  onEscalate: (alertId: string) => void;
}

export interface ReportsScreenProps {
  childId?: string;
  initialPeriod?: 'daily' | 'weekly' | 'monthly';
}

export interface ChildCardProps {
  child: ChildProfile;
  onSelect: (childId: string) => void;
  onEdit: (childId: string) => void;
  showActions?: boolean;
}

export interface SubscriptionCardProps {
  tier: SubscriptionTier;
  current?: boolean;
  onSelect: (tierId: string) => void;
  showTrialBadge?: boolean;
}

// =============================================================================
// WEBSOCKET TYPES
// =============================================================================

export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
  id?: string;
}

export interface WebSocketConnectionState {
  connected: boolean;
  connecting: boolean;
  reconnectAttempts: number;
  lastConnected?: string;
  lastError?: string;
}

export interface WebSocketEventHandlers {
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: string) => void;
  onAlert?: (alert: SafetyAlert) => void;
  onInteraction?: (interaction: Interaction) => void;
  onMessage?: (message: WebSocketMessage) => void;
}

// =============================================================================
// UTILITY TYPES
// =============================================================================

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  errors?: string[];
}

export interface PaginationInfo {
  page: number;
  limit: number;
  total: number;
  hasNext: boolean;
  hasPrev: boolean;
}

export interface FilterOptions {
  dateFrom?: string;
  dateTo?: string;
  childIds?: string[];
  severity?: string[];
  resolved?: boolean;
  limit?: number;
  offset?: number;
}

export interface AppState {
  user: User | null;
  children: ChildProfile[];
  activeAlerts: SafetyAlert[];
  subscription: UserSubscription | null;
  loading: boolean;
  error: string | null;
}

export interface NavigationParamList {
  Home: undefined;
  Login: undefined;
  Dashboard: undefined;
  Children: undefined;
  ChildDetail: { childId: string };
  Reports: { childId?: string };
  Alerts: undefined;
  AlertDetail: { alertId: string };
  Settings: undefined;
  Subscription: undefined;
  Profile: undefined;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

export function isSafetyAlert(obj: any): obj is SafetyAlert {
  return obj && 
         typeof obj.id === 'string' &&
         typeof obj.child_id === 'string' &&
         typeof obj.type === 'string' &&
         typeof obj.severity === 'string' &&
         typeof obj.message === 'string';
}

export function isChild(obj: any): obj is Child {
  return obj && 
         typeof obj.id === 'string' &&
         typeof obj.name === 'string' &&
         typeof obj.age === 'number';
}

export function isInteraction(obj: any): obj is Interaction {
  return obj && 
         typeof obj.id === 'string' &&
         typeof obj.child_id === 'string' &&
         typeof obj.question === 'string' &&
         typeof obj.response === 'string' &&
         typeof obj.timestamp === 'string';
}

export function isChildProfile(obj: any): obj is ChildProfile {
  return obj && 
         typeof obj.id === 'string' &&
         typeof obj.name === 'string' &&
         typeof obj.age === 'number' &&
         obj.safety_settings !== undefined &&
         obj.usage_limits !== undefined;
}

export function isSubscriptionTier(obj: any): obj is SubscriptionTier {
  return obj && 
         typeof obj.id === 'string' &&
         typeof obj.name === 'string' &&
         typeof obj.price_monthly_iqd === 'number' &&
         Array.isArray(obj.features);
}

// =============================================================================
// CONSTANTS
// =============================================================================

export const ALERT_SEVERITIES = ['low', 'medium', 'high', 'critical'] as const;
export const ALERT_TYPES = ['forbidden_content', 'self_harm', 'excessive_usage', 'inappropriate_interaction', 'emergency'] as const;
export const SUBSCRIPTION_STATUSES = ['active', 'cancelled', 'expired', 'trial'] as const;
export const PAYMENT_METHODS = ['zaincash', 'asiacell', 'credit_card', 'bank_transfer'] as const;
export const CONTENT_FILTER_LEVELS = ['strict', 'moderate', 'basic'] as const;
export const BILLING_CYCLES = ['monthly', 'yearly'] as const;

export type AlertSeverity = typeof ALERT_SEVERITIES[number];
export type AlertType = typeof ALERT_TYPES[number];
export type SubscriptionStatus = typeof SUBSCRIPTION_STATUSES[number];
export type PaymentMethodType = typeof PAYMENT_METHODS[number];
export type ContentFilterLevel = typeof CONTENT_FILTER_LEVELS[number];
export type BillingCycle = typeof BILLING_CYCLES[number];
