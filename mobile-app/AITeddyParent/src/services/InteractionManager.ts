/**
 * Interaction Manager - إدارة شاملة للتفاعلات والمحادثات
 * 
 * Features:
 * - CRUD operations for interactions
 * - Content filtering and moderation
 * - Conversation context tracking
 * - Audit logging and compliance
 * - Real-time interaction monitoring
 * - Bulk operations and analytics
 * 
 * @version 1.0.0
 * @since 2025-08-04
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { EventEmitter } from 'events';
import { ApiService } from './api';
import { AlertService } from './AlertService';
import { MultiChildManager } from './MultiChildManager';

export interface Interaction {
  id: string;
  child_id: string;
  child_name: string;
  conversation_id: string;
  user_message: string;
  ai_response: string;
  timestamp: string;
  duration_seconds: number;
  has_forbidden_content: boolean;
  content_flags: ContentFlag[];
  sentiment_score: number; // -1 to 1
  safety_rating: 'safe' | 'caution' | 'warning' | 'danger';
  context: InteractionContext;
  metadata: InteractionMetadata;
  is_archived: boolean;
  parent_reviewed: boolean;
  review_notes?: string;
}

export interface ContentFlag {
  type: 'inappropriate_language' | 'violence' | 'adult_content' | 'personal_info' | 'bullying' | 'self_harm';
  severity: 'low' | 'medium' | 'high' | 'critical';
  confidence: number; // 0-1
  detected_text?: string;
  ai_explanation: string;
}

export interface InteractionContext {
  conversation_turn: number;
  topic_category: string;
  emotional_state: 'happy' | 'sad' | 'angry' | 'confused' | 'excited' | 'neutral';
  previous_interactions_count: number;
  session_duration_minutes: number;
  time_of_day: 'morning' | 'afternoon' | 'evening' | 'night';
  is_follow_up: boolean;
  parent_presence: boolean;
}

export interface InteractionMetadata {
  device_type: string;
  app_version: string;
  ai_model_version: string;
  response_time_ms: number;
  language_detected: string;
  processing_flags: string[];
  compliance_tags: string[];
  quality_score: number; // 0-100
}

export interface ConversationSummary {
  id: string;
  child_id: string;
  start_time: string;
  end_time: string;
  total_interactions: number;
  duration_minutes: number;
  topics_discussed: string[];
  safety_incidents: number;
  overall_sentiment: number;
  key_insights: string[];
  parent_attention_required: boolean;
}

export interface InteractionFilter {
  child_ids?: string[];
  date_from?: string;
  date_to?: string;
  has_forbidden_content?: boolean;
  safety_ratings?: string[];
  content_flag_types?: string[];
  sentiment_range?: { min: number; max: number };
  parent_reviewed?: boolean;
  conversation_ids?: string[];
  topics?: string[];
  limit?: number;
  offset?: number;
}

export interface BulkOperation {
  operation: 'archive' | 'delete' | 'mark_reviewed' | 'flag_content' | 'export';
  interaction_ids: string[];
  parameters?: any;
}

export class InteractionManager extends EventEmitter {
  private static instance: InteractionManager;
  private alertService: AlertService;
  private multiChildManager: MultiChildManager;
  private interactions: Map<string, Interaction> = new Map();
  private conversations: Map<string, ConversationSummary> = new Map();
  private isMonitoring: boolean = false;
  private auditLog: any[] = [];

  private constructor() {
    super();
    this.alertService = AlertService.getInstance();
    this.multiChildManager = MultiChildManager.getInstance();
    this.loadStoredData();
  }

  public static getInstance(): InteractionManager {
    if (!InteractionManager.instance) {
      InteractionManager.instance = new InteractionManager();
    }
    return InteractionManager.instance;
  }

  /**
   * إنشاء تفاعل جديد
   */
  public async createInteraction(interactionData: Omit<Interaction, 'id' | 'timestamp'>): Promise<Interaction> {
    try {
      console.log('💬 Creating new interaction for child:', interactionData.child_id);

      const interaction: Interaction = {
        ...interactionData,
        id: `interaction_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        timestamp: new Date().toISOString()
      };

      // فحص المحتوى والأمان
      await this.analyzeInteractionContent(interaction);

      // حفظ التفاعل
      await this.saveInteraction(interaction);

      // تحديث سياق المحادثة
      await this.updateConversationContext(interaction);

      // مراقبة الأمان
      if (interaction.has_forbidden_content || interaction.safety_rating !== 'safe') {
        await this.handleUnsafeInteraction(interaction);
      }

      // إشعار بالتفاعل الجديد
      this.emit('interaction_created', interaction);

      // تسجيل في سجل المراجعة
      await this.logAuditEvent('interaction_created', {
        interaction_id: interaction.id,
        child_id: interaction.child_id,
        safety_rating: interaction.safety_rating
      });

      console.log('✅ Interaction created successfully:', interaction.id);
      return interaction;

    } catch (error) {
      console.error('❌ Error creating interaction:', error);
      throw error;
    }
  }

  /**
   * تحديث تفاعل موجود
   */
  public async updateInteraction(
    interactionId: string, 
    updates: Partial<Interaction>
  ): Promise<Interaction | null> {
    try {
      console.log('📝 Updating interaction:', interactionId);

      const currentInteraction = await this.getInteraction(interactionId);
      if (!currentInteraction) {
        throw new Error('Interaction not found');
      }

      const updatedInteraction: Interaction = {
        ...currentInteraction,
        ...updates
      };

      // إعادة تحليل المحتوى إذا تم تغيير الرسائل
      if (updates.user_message || updates.ai_response) {
        await this.analyzeInteractionContent(updatedInteraction);
      }

      await this.saveInteraction(updatedInteraction);

      this.emit('interaction_updated', { interactionId, updates });

      await this.logAuditEvent('interaction_updated', {
        interaction_id: interactionId,
        updates: Object.keys(updates)
      });

      console.log('✅ Interaction updated successfully');
      return updatedInteraction;

    } catch (error) {
      console.error('❌ Error updating interaction:', error);
      throw error;
    }
  }

  /**
   * حذف تفاعل
   */
  public async deleteInteraction(interactionId: string, permanent: boolean = false): Promise<boolean> {
    try {
      console.log(`🗑️ ${permanent ? 'Permanently deleting' : 'Archiving'} interaction:`, interactionId);

      const interaction = await this.getInteraction(interactionId);
      if (!interaction) {
        throw new Error('Interaction not found');
      }

      if (permanent) {
        // حذف نهائي
        this.interactions.delete(interactionId);
        await AsyncStorage.removeItem(`interaction_${interactionId}`);
        
        // حذف من السيرفر
        // await ApiService.deleteInteraction(interactionId);
      } else {
        // أرشفة فقط
        await this.updateInteraction(interactionId, { is_archived: true });
      }

      this.emit('interaction_deleted', { interactionId, permanent });

      await this.logAuditEvent('interaction_deleted', {
        interaction_id: interactionId,
        permanent,
        child_id: interaction.child_id
      });

      console.log('✅ Interaction deleted successfully');
      return true;

    } catch (error) {
      console.error('❌ Error deleting interaction:', error);
      throw error;
    }
  }

  /**
   * الحصول على تفاعل محدد
   */
  public async getInteraction(interactionId: string): Promise<Interaction | null> {
    try {
      // البحث في الذاكرة أولاً
      if (this.interactions.has(interactionId)) {
        return this.interactions.get(interactionId) || null;
      }

      // البحث في التخزين المحلي
      const stored = await AsyncStorage.getItem(`interaction_${interactionId}`);
      if (stored) {
        const interaction = JSON.parse(stored);
        this.interactions.set(interactionId, interaction);
        return interaction;
      }

      // محاولة الجلب من السيرفر
      try {
        const interactions = await ApiService.getChildInteractions('', 1000);
        const interaction = interactions.find(i => i.id === interactionId);
        if (interaction) {
          const mappedInteraction = this.mapApiInteractionToLocal(interaction);
          await this.saveInteraction(mappedInteraction);
          return mappedInteraction;
        }
      } catch (apiError) {
        console.warn('⚠️ Could not fetch from server:', apiError);
      }

      return null;

    } catch (error) {
      console.error('❌ Error getting interaction:', error);
      return null;
    }
  }

  /**
   * البحث في التفاعلات بفلاتر
   */
  public async searchInteractions(filter: InteractionFilter): Promise<Interaction[]> {
    try {
      console.log('🔍 Searching interactions with filter:', filter);

      // جلب جميع التفاعلات المحلية
      await this.loadAllInteractions();

      let results = Array.from(this.interactions.values());

      // تطبيق الفلاتر
      if (filter.child_ids && filter.child_ids.length > 0) {
        results = results.filter(i => filter.child_ids!.includes(i.child_id));
      }

      if (filter.date_from) {
        const fromDate = new Date(filter.date_from);
        results = results.filter(i => new Date(i.timestamp) >= fromDate);
      }

      if (filter.date_to) {
        const toDate = new Date(filter.date_to);
        results = results.filter(i => new Date(i.timestamp) <= toDate);
      }

      if (filter.has_forbidden_content !== undefined) {
        results = results.filter(i => i.has_forbidden_content === filter.has_forbidden_content);
      }

      if (filter.safety_ratings && filter.safety_ratings.length > 0) {
        results = results.filter(i => filter.safety_ratings!.includes(i.safety_rating));
      }

      if (filter.content_flag_types && filter.content_flag_types.length > 0) {
        results = results.filter(i => 
          i.content_flags.some(flag => filter.content_flag_types!.includes(flag.type))
        );
      }

      if (filter.sentiment_range) {
        const { min, max } = filter.sentiment_range;
        results = results.filter(i => i.sentiment_score >= min && i.sentiment_score <= max);
      }

      if (filter.parent_reviewed !== undefined) {
        results = results.filter(i => i.parent_reviewed === filter.parent_reviewed);
      }

      if (filter.conversation_ids && filter.conversation_ids.length > 0) {
        results = results.filter(i => filter.conversation_ids!.includes(i.conversation_id));
      }

      if (filter.topics && filter.topics.length > 0) {
        results = results.filter(i => 
          filter.topics!.some(topic => i.context.topic_category.includes(topic))
        );
      }

      // ترتيب بالتاريخ (الأحدث أولاً)
      results.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

      // تطبيق التصفح
      const offset = filter.offset || 0;
      const limit = filter.limit || 50;
      results = results.slice(offset, offset + limit);

      console.log(`✅ Found ${results.length} interactions matching filter`);
      return results;

    } catch (error) {
      console.error('❌ Error searching interactions:', error);
      return [];
    }
  }

  /**
   * الحصول على تفاعلات طفل محدد
   */
  public async getChildInteractions(
    childId: string, 
    limit: number = 50,
    includeArchived: boolean = false
  ): Promise<Interaction[]> {
    return this.searchInteractions({
      child_ids: [childId],
      limit,
      offset: 0
    }).then(results => 
      includeArchived ? results : results.filter(i => !i.is_archived)
    );
  }

  /**
   * الحصول على ملخص المحادثة
   */
  public async getConversationSummary(conversationId: string): Promise<ConversationSummary | null> {
    try {
      // البحث في الكاش أولاً
      if (this.conversations.has(conversationId)) {
        return this.conversations.get(conversationId) || null;
      }

      // إنشاء ملخص جديد من التفاعلات
      const interactions = await this.searchInteractions({
        conversation_ids: [conversationId],
        limit: 1000
      });

      if (interactions.length === 0) {
        return null;
      }

      const summary = await this.generateConversationSummary(conversationId, interactions);
      this.conversations.set(conversationId, summary);
      
      return summary;

    } catch (error) {
      console.error('❌ Error getting conversation summary:', error);
      return null;
    }
  }

  /**
   * مراجعة تفاعل من قبل الوالدين
   */
  public async reviewInteraction(
    interactionId: string, 
    approved: boolean, 
    notes?: string
  ): Promise<boolean> {
    try {
      console.log('👀 Parent reviewing interaction:', interactionId);

      const updates: Partial<Interaction> = {
        parent_reviewed: true,
        review_notes: notes
      };

      await this.updateInteraction(interactionId, updates);

      this.emit('interaction_reviewed', { 
        interactionId, 
        approved, 
        notes 
      });

      await this.logAuditEvent('interaction_reviewed', {
        interaction_id: interactionId,
        approved,
        reviewer: 'parent'
      });

      console.log('✅ Interaction reviewed successfully');
      return true;

    } catch (error) {
      console.error('❌ Error reviewing interaction:', error);
      throw error;
    }
  }

  /**
   * تنفيذ عمليات مجمعة
   */
  public async performBulkOperation(operation: BulkOperation): Promise<boolean> {
    try {
      console.log(`🔄 Performing bulk operation: ${operation.operation} on ${operation.interaction_ids.length} interactions`);

      const results: boolean[] = [];

      for (const interactionId of operation.interaction_ids) {
        try {
          let success = false;

          switch (operation.operation) {
            case 'archive':
              success = await this.updateInteraction(interactionId, { is_archived: true }) !== null;
              break;

            case 'delete':
              success = await this.deleteInteraction(interactionId, operation.parameters?.permanent || false);
              break;

            case 'mark_reviewed':
              success = await this.reviewInteraction(
                interactionId, 
                operation.parameters?.approved || true, 
                operation.parameters?.notes
              );
              break;

            case 'flag_content':
              const interaction = await this.getInteraction(interactionId);
              if (interaction) {
                const newFlag: ContentFlag = {
                  type: operation.parameters?.flag_type || 'inappropriate_language',
                  severity: operation.parameters?.severity || 'medium',
                  confidence: operation.parameters?.confidence || 0.8,
                  ai_explanation: operation.parameters?.explanation || 'Flagged by bulk operation'
                };
                
                success = await this.updateInteraction(interactionId, {
                  content_flags: [...interaction.content_flags, newFlag],
                  has_forbidden_content: true
                }) !== null;
              }
              break;

            case 'export':
              // سيتم تنفيذ تصدير البيانات لاحقاً
              success = true;
              break;
          }

          results.push(success);

        } catch (error) {
          console.error(`❌ Error processing interaction ${interactionId}:`, error);
          results.push(false);
        }
      }

      const successCount = results.filter(r => r).length;
      const failureCount = results.length - successCount;

      this.emit('bulk_operation_completed', {
        operation: operation.operation,
        total: operation.interaction_ids.length,
        success: successCount,
        failures: failureCount
      });

      await this.logAuditEvent('bulk_operation', {
        operation: operation.operation,
        total_items: operation.interaction_ids.length,
        success_count: successCount,
        failure_count: failureCount
      });

      console.log(`✅ Bulk operation completed: ${successCount}/${operation.interaction_ids.length} successful`);
      return failureCount === 0;

    } catch (error) {
      console.error('❌ Error performing bulk operation:', error);
      throw error;
    }
  }

  /**
   * تحليل محتوى التفاعل
   */
  private async analyzeInteractionContent(interaction: Interaction): Promise<void> {
    try {
      // تحليل المحتوى المحظور (محاكاة AI)
      const contentFlags = await this.detectContentFlags(interaction);
      interaction.content_flags = contentFlags;
      interaction.has_forbidden_content = contentFlags.length > 0;

      // تحليل المشاعر
      interaction.sentiment_score = this.analyzeSentiment(interaction.user_message, interaction.ai_response);

      // تحديد تقييم الأمان
      interaction.safety_rating = this.calculateSafetyRating(interaction);

      // تحليل السياق العاطفي
      interaction.context.emotional_state = this.detectEmotionalState(interaction.user_message);

      // حساب درجة الجودة
      interaction.metadata.quality_score = this.calculateQualityScore(interaction);

    } catch (error) {
      console.error('❌ Error analyzing interaction content:', error);
      // تعيين قيم افتراضية آمنة
      interaction.content_flags = [];
      interaction.has_forbidden_content = false;
      interaction.sentiment_score = 0;
      interaction.safety_rating = 'safe';
      interaction.metadata.quality_score = 50;
    }
  }

  private async detectContentFlags(interaction: Interaction): Promise<ContentFlag[]> {
    const flags: ContentFlag[] = [];
    const combinedText = `${interaction.user_message} ${interaction.ai_response}`.toLowerCase();

    // قائمة الكلمات المحظورة (مبسطة للمثال)
    const inappropriateWords = ['كلمة سيئة', 'عنف', 'إيذاء'];
    const violenceWords = ['قتل', 'ضرب', 'عنف'];
    const personalInfoPatterns = [/\d{3}-\d{3}-\d{4}/, /\w+@\w+\.\w+/]; // أرقام هاتف وإيميل

    // فحص الكلمات غير المناسبة
    for (const word of inappropriateWords) {
      if (combinedText.includes(word)) {
        flags.push({
          type: 'inappropriate_language',
          severity: 'medium',
          confidence: 0.8,
          detected_text: word,
          ai_explanation: `تم اكتشاف كلمة غير مناسبة: ${word}`
        });
      }
    }

    // فحص العنف
    for (const word of violenceWords) {
      if (combinedText.includes(word)) {
        flags.push({
          type: 'violence',
          severity: 'high',
          confidence: 0.9,
          detected_text: word,
          ai_explanation: `تم اكتشاف محتوى عنيف: ${word}`
        });
      }
    }

    // فحص المعلومات الشخصية
    for (const pattern of personalInfoPatterns) {
      const match = combinedText.match(pattern);
      if (match) {
        flags.push({
          type: 'personal_info',
          severity: 'high',
          confidence: 0.95,
          detected_text: match[0],
          ai_explanation: 'تم اكتشاف معلومات شخصية محتملة'
        });
      }
    }

    return flags;
  }

  private analyzeSentiment(userMessage: string, aiResponse: string): number {
    // محاكاة تحليل المشاعر (في التطبيق الحقيقي سيستخدم AI)
    const positiveWords = ['سعيد', 'رائع', 'ممتاز', 'أحب', 'جميل'];
    const negativeWords = ['حزين', 'سيء', 'أكره', 'غاضب', 'مؤلم'];

    const text = `${userMessage} ${aiResponse}`.toLowerCase();
    let score = 0;

    positiveWords.forEach(word => {
      if (text.includes(word)) score += 0.2;
    });

    negativeWords.forEach(word => {
      if (text.includes(word)) score -= 0.2;
    });

    return Math.max(-1, Math.min(1, score));
  }

  private calculateSafetyRating(interaction: Interaction): 'safe' | 'caution' | 'warning' | 'danger' {
    if (interaction.content_flags.length === 0) {
      return 'safe';
    }

    const criticalFlags = interaction.content_flags.filter(f => f.severity === 'critical');
    const highFlags = interaction.content_flags.filter(f => f.severity === 'high');

    if (criticalFlags.length > 0) {
      return 'danger';
    }

    if (highFlags.length > 0) {
      return 'warning';
    }

    return 'caution';
  }

  private detectEmotionalState(message: string): 'happy' | 'sad' | 'angry' | 'confused' | 'excited' | 'neutral' {
    const text = message.toLowerCase();

    if (text.includes('سعيد') || text.includes('مبسوط')) return 'happy';
    if (text.includes('حزين') || text.includes('مؤلم')) return 'sad';
    if (text.includes('غاضب') || text.includes('زعلان')) return 'angry';
    if (text.includes('متحمس') || text.includes('متشوق')) return 'excited';
    if (text.includes('محتار') || text.includes('مش فاهم')) return 'confused';

    return 'neutral';
  }

  private calculateQualityScore(interaction: Interaction): number {
    let score = 100;

    // خصم نقاط للمحتوى المحظور
    score -= interaction.content_flags.length * 20;

    // خصم نقاط للمشاعر السلبية الشديدة
    if (interaction.sentiment_score < -0.5) {
      score -= 15;
    }

    // خصم نقاط للرسائل القصيرة جداً
    if (interaction.user_message.length < 10) {
      score -= 10;
    }

    // خصم نقاط لعدم وجود سياق
    if (interaction.context.conversation_turn === 1) {
      score -= 5;
    }

    return Math.max(0, Math.min(100, score));
  }

  private async handleUnsafeInteraction(interaction: Interaction): Promise<void> {
    console.log('⚠️ Handling unsafe interaction:', interaction.id);

    // إنشاء تنبيه أمان
    const alertSeverity = this.mapSafetyRatingToAlertSeverity(interaction.safety_rating);
    
    this.alertService.addNewAlert({
      id: `alert_${Date.now()}`,
      child_id: interaction.child_id,
      child_name: interaction.child_name,
      type: 'forbidden_content',
      severity: alertSeverity,
      message: `تم اكتشاف محتوى غير آمن في محادثة ${interaction.child_name}`,
      details: this.generateInteractionSummary(interaction),
      timestamp: new Date().toISOString(),
      resolved: false,
      risk_score: this.calculateRiskScore(interaction),
      auto_resolved: false,
      requires_immediate_action: interaction.safety_rating === 'danger',
      escalation_level: interaction.safety_rating === 'danger' ? 3 : 2,
      context: {
        conversation_id: interaction.conversation_id,
        message_content: interaction.user_message.substring(0, 100),
        interaction_duration: interaction.duration_seconds
      }
    });

    // إشعار فوري للوالدين إذا كان خطيراً
    if (interaction.safety_rating === 'danger') {
      this.emit('critical_interaction_detected', interaction);
    }
  }

  private mapSafetyRatingToAlertSeverity(rating: string): 'low' | 'medium' | 'high' | 'critical' {
    switch (rating) {
      case 'danger': return 'critical';
      case 'warning': return 'high';
      case 'caution': return 'medium';
      default: return 'low';
    }
  }

  private calculateRiskScore(interaction: Interaction): number {
    let score = 0;

    // نقاط حسب تقييم الأمان
    switch (interaction.safety_rating) {
      case 'danger': score += 80; break;
      case 'warning': score += 60; break;
      case 'caution': score += 30; break;
      default: score += 5; break;
    }

    // نقاط إضافية حسب عدد العلامات
    score += interaction.content_flags.length * 10;

    // نقاط للمشاعر السلبية
    if (interaction.sentiment_score < -0.5) {
      score += 15;
    }

    return Math.min(100, score);
  }

  private generateInteractionSummary(interaction: Interaction): string {
    const flags = interaction.content_flags.map(f => f.type).join(', ');
    return `رسالة الطفل: "${interaction.user_message.substring(0, 50)}..." | العلامات المكتشفة: ${flags} | تقييم الأمان: ${interaction.safety_rating}`;
  }

  private async generateConversationSummary(
    conversationId: string, 
    interactions: Interaction[]
  ): Promise<ConversationSummary> {
    const sortedInteractions = interactions.sort((a, b) => 
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    const firstInteraction = sortedInteractions[0];
    const lastInteraction = sortedInteractions[sortedInteractions.length - 1];

    const startTime = new Date(firstInteraction.timestamp);
    const endTime = new Date(lastInteraction.timestamp);
    const durationMinutes = Math.round((endTime.getTime() - startTime.getTime()) / (1000 * 60));

    const topics = [...new Set(interactions.map(i => i.context.topic_category))];
    const safetyIncidents = interactions.filter(i => i.has_forbidden_content).length;
    const avgSentiment = interactions.reduce((sum, i) => sum + i.sentiment_score, 0) / interactions.length;

    const keyInsights = this.generateKeyInsights(interactions);
    const needsAttention = safetyIncidents > 0 || avgSentiment < -0.3 || 
                          interactions.some(i => i.safety_rating === 'warning' || i.safety_rating === 'danger');

    return {
      id: conversationId,
      child_id: firstInteraction.child_id,
      start_time: firstInteraction.timestamp,
      end_time: lastInteraction.timestamp,
      total_interactions: interactions.length,
      duration_minutes: durationMinutes,
      topics_discussed: topics,
      safety_incidents: safetyIncidents,
      overall_sentiment: avgSentiment,
      key_insights: keyInsights,
      parent_attention_required: needsAttention
    };
  }

  private generateKeyInsights(interactions: Interaction[]): string[] {
    const insights: string[] = [];

    // تحليل طول المحادثة
    if (interactions.length > 20) {
      insights.push('محادثة طويلة تتطلب مراجعة');
    }

    // تحليل المشاعر
    const avgSentiment = interactions.reduce((sum, i) => sum + i.sentiment_score, 0) / interactions.length;
    if (avgSentiment > 0.5) {
      insights.push('محادثة إيجابية بشكل عام');
    } else if (avgSentiment < -0.3) {
      insights.push('محادثة تحتوي على مشاعر سلبية');
    }

    // تحليل الموضوعات
    const topics = [...new Set(interactions.map(i => i.context.topic_category))];
    if (topics.length > 5) {
      insights.push('تنوع كبير في الموضوعات المناقشة');
    }

    // تحليل الأمان
    const unsafeCount = interactions.filter(i => i.safety_rating !== 'safe').length;
    if (unsafeCount > 0) {
      insights.push(`${unsafeCount} تفاعل يتطلب انتباه أمني`);
    }

    return insights;
  }

  private async updateConversationContext(interaction: Interaction): Promise<void> {
    // تحديث عدد التفاعلات في المحادثة
    const conversationInteractions = await this.searchInteractions({
      conversation_ids: [interaction.conversation_id],
      limit: 1000
    });

    interaction.context.conversation_turn = conversationInteractions.length;
    interaction.context.previous_interactions_count = conversationInteractions.length - 1;

    // تحديث معرف هل هذا تفاعل متابعة
    interaction.context.is_follow_up = interaction.context.conversation_turn > 1;

    // حفظ السياق المحدث
    await this.saveInteraction(interaction);
  }

  private mapApiInteractionToLocal(apiInteraction: any): Interaction {
    return {
      id: apiInteraction.id,
      child_id: apiInteraction.child_id,
      child_name: apiInteraction.child_name || 'غير معروف',
      conversation_id: apiInteraction.conversation_id || `conv_${apiInteraction.id}`,
      user_message: apiInteraction.user_message,
      ai_response: apiInteraction.ai_response,
      timestamp: apiInteraction.timestamp,
      duration_seconds: apiInteraction.duration_seconds || 0,
      has_forbidden_content: apiInteraction.has_forbidden_content || false,
      content_flags: [],
      sentiment_score: 0,
      safety_rating: 'safe',
      context: {
        conversation_turn: 1,
        topic_category: 'general',
        emotional_state: 'neutral',
        previous_interactions_count: 0,
        session_duration_minutes: 0,
        time_of_day: this.getTimeOfDay(),
        is_follow_up: false,
        parent_presence: false
      },
      metadata: {
        device_type: 'mobile',
        app_version: '1.0.0',
        ai_model_version: '1.0.0',
        response_time_ms: 0,
        language_detected: 'ar',
        processing_flags: [],
        compliance_tags: ['COPPA'],
        quality_score: 70
      },
      is_archived: false,
      parent_reviewed: false
    };
  }

  private getTimeOfDay(): 'morning' | 'afternoon' | 'evening' | 'night' {
    const hour = new Date().getHours();
    if (hour >= 6 && hour < 12) return 'morning';
    if (hour >= 12 && hour < 17) return 'afternoon';
    if (hour >= 17 && hour < 21) return 'evening';
    return 'night';
  }

  private async saveInteraction(interaction: Interaction): Promise<void> {
    // حفظ في الذاكرة
    this.interactions.set(interaction.id, interaction);

    // حفظ محلياً
    await AsyncStorage.setItem(`interaction_${interaction.id}`, JSON.stringify(interaction));

    // مزامنة مع السيرفر (محاكاة)
    console.log('🔄 Would sync interaction to server:', interaction.id);
  }

  private async loadStoredData(): Promise<void> {
    try {
      // جلب التفاعلات المحفوظة
      const keys = await AsyncStorage.getAllKeys();
      const interactionKeys = keys.filter(key => key.startsWith('interaction_'));

      for (const key of interactionKeys.slice(0, 100)) { // تحديد العدد لتجنب الحمل الزائد
        const data = await AsyncStorage.getItem(key);
        if (data) {
          const interaction = JSON.parse(data);
          this.interactions.set(interaction.id, interaction);
        }
      }

      console.log(`✅ Loaded ${this.interactions.size} interactions from storage`);
    } catch (error) {
      console.error('❌ Error loading stored data:', error);
    }
  }

  private async loadAllInteractions(): Promise<void> {
    if (this.interactions.size < 100) { // جلب المزيد إذا كان العدد قليل
      try {
        const keys = await AsyncStorage.getAllKeys();
        const interactionKeys = keys.filter(key => key.startsWith('interaction_'));

        for (const key of interactionKeys) {
          if (!this.interactions.has(key.replace('interaction_', ''))) {
            const data = await AsyncStorage.getItem(key);
            if (data) {
              const interaction = JSON.parse(data);
              this.interactions.set(interaction.id, interaction);
            }
          }
        }
      } catch (error) {
        console.error('❌ Error loading all interactions:', error);
      }
    }
  }

  private async logAuditEvent(action: string, details: any): Promise<void> {
    const auditEntry = {
      id: `audit_${Date.now()}`,
      action,
      details,
      timestamp: new Date().toISOString(),
      user: 'parent' // سيتم تحديثه حسب المستخدم الحالي
    };

    this.auditLog.unshift(auditEntry);

    // الحفاظ على آخر 1000 سجل فقط
    if (this.auditLog.length > 1000) {
      this.auditLog = this.auditLog.slice(0, 1000);
    }

    // حفظ سجل المراجعة
    try {
      await AsyncStorage.setItem('audit_log', JSON.stringify(this.auditLog));
    } catch (error) {
      console.error('❌ Error saving audit log:', error);
    }
  }

  /**
   * تنظيف الموارد
   */
  public async cleanup(): Promise<void> {
    this.interactions.clear();
    this.conversations.clear();
    this.auditLog = [];
    this.isMonitoring = false;
    this.removeAllListeners();
    
    console.log('✅ InteractionManager cleanup completed');
  }
}

export default InteractionManager;
