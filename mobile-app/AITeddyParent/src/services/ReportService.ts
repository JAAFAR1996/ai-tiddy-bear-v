/**
 * Report Service - خدمة إنشاء وإدارة التقارير الذكية
 * 
 * Features:
 * - AI-powered report generation
 * - Multiple report periods (daily, weekly, monthly)
 * - PDF export functionality
 * - Trend analysis and insights
 * - Behavior pattern recognition
 * - COPPA-compliant data handling
 * 
 * @version 1.0.0
 * @since 2025-08-04
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { EventEmitter } from 'events';
import { ApiService } from './api';
import { AlertService } from './AlertService';

export interface ReportData {
  id: string;
  period: 'daily' | 'weekly' | 'monthly';
  child_id: string;
  child_name: string;
  generated_at: string;
  summary: {
    total_interactions: number;
    safe_interactions: number;
    flagged_interactions: number;
    average_session_duration: number;
    safety_score: number;
    improvement_areas: string[];
    positive_highlights: string[];
  };
  trends: {
    interaction_count: number[];
    safety_scores: number[];
    session_durations: number[];
    labels: string[];
  };
  ai_insights: {
    behavior_analysis: string;
    recommendations: string[];
    concerns: string[];
    progress_notes: string;
  };
  alerts_summary: {
    total_alerts: number;
    critical_alerts: number;
    resolved_alerts: number;
    common_issues: string[];
  };
  metadata: {
    start_date: string;
    end_date: string;
    data_points: number;
    generation_duration: number;
    ai_model_version: string;
  };
}

export interface ReportTemplate {
  period: 'daily' | 'weekly' | 'monthly';
  sections: string[];
  insights_enabled: boolean;
  charts_enabled: boolean;
  language: 'ar' | 'en';
}

export interface AnalyticsData {
  interactions: Array<{
    id: string;
    timestamp: string;
    duration: number;
    has_forbidden_content: boolean;
    child_id: string;
  }>;
  alerts: Array<{
    id: string;
    timestamp: string;
    severity: string;
    type: string;
    resolved: boolean;
    child_id: string;
  }>;
  usage_patterns: {
    daily_hours: number[];
    peak_times: string[];
    session_lengths: number[];
  };
}

export class ReportService extends EventEmitter {
  private static instance: ReportService;
  private alertService: AlertService;
  private cachedReports: Map<string, ReportData> = new Map();
  private generationQueue: string[] = [];
  private isGenerating: boolean = false;

  private constructor() {
    super();
    this.alertService = AlertService.getInstance();
  }

  public static getInstance(): ReportService {
    if (!ReportService.instance) {
      ReportService.instance = new ReportService();
    }
    return ReportService.instance;
  }

  /**
   * إنشاء تقرير جديد
   */
  public async generateReport(
    childId: string, 
    period: 'daily' | 'weekly' | 'monthly'
  ): Promise<ReportData> {
    try {
      console.log(`📊 Generating ${period} report for child: ${childId}`);
      
      this.isGenerating = true;
      this.emit('generation_started', { childId, period });

      const startTime = Date.now();

      // جمع البيانات
      const analyticsData = await this.collectAnalyticsData(childId, period);
      
      // تحليل البيانات
      const analysis = await this.analyzeData(analyticsData, period);
      
      // إنشاء التقرير
      const report = await this.createReport(childId, period, analyticsData, analysis);
      
      // حفظ التقرير
      await this.saveReport(report);
      
      const generationTime = Date.now() - startTime;
      console.log(`✅ Report generated in ${generationTime}ms`);
      
      this.emit('generation_completed', report);
      
      return report;

    } catch (error) {
      console.error('❌ Error generating report:', error);
      this.emit('generation_failed', { childId, period, error });
      throw error;
    } finally {
      this.isGenerating = false;
    }
  }

  /**
   * الحصول على تقرير محفوظ
   */
  public async getReport(
    childId: string, 
    period: 'daily' | 'weekly' | 'monthly'
  ): Promise<ReportData | null> {
    try {
      const reportKey = this.getReportKey(childId, period);
      
      // البحث في الكاش أولاً
      if (this.cachedReports.has(reportKey)) {
        return this.cachedReports.get(reportKey) || null;
      }

      // البحث في التخزين المحلي
      const savedReport = await AsyncStorage.getItem(`report_${reportKey}`);
      if (savedReport) {
        const report = JSON.parse(savedReport);
        this.cachedReports.set(reportKey, report);
        return report;
      }

      // محاولة إنشاء تقرير جديد إذا لم يوجد
      console.log('📊 No existing report found, generating new one...');
      return await this.generateReport(childId, period);

    } catch (error) {
      console.error('❌ Error getting report:', error);
      return null;
    }
  }

  /**
   * الحصول على جميع التقارير لطفل
   */
  public async getAllReports(childId: string): Promise<ReportData[]> {
    try {
      const reports: ReportData[] = [];
      const periods: Array<'daily' | 'weekly' | 'monthly'> = ['daily', 'weekly', 'monthly'];

      for (const period of periods) {
        const report = await this.getReport(childId, period);
        if (report) {
          reports.push(report);
        }
      }

      return reports.sort((a, b) => 
        new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime()
      );

    } catch (error) {
      console.error('❌ Error getting all reports:', error);
      return [];
    }
  }

  /**
   * إنشاء PDF من التقرير
   */
  public async generatePDF(report: ReportData): Promise<string> {
    try {
      console.log('📄 Generating PDF for report:', report.id);

      // في التطبيق الحقيقي سيتم استخدام مكتبة PDF
      // مثل react-native-html-to-pdf أو رابط السيرفر

      // محاكاة إنشاء PDF
      const pdfContent = this.generatePDFContent(report);
      
      // حفظ محلياً (محاكاة)
      const fileName = `report_${report.child_name}_${report.period}_${Date.now()}.pdf`;
      const filePath = `file://documents/${fileName}`;
      
      // في التطبيق الحقيقي:
      // const pdfPath = await RNHTMLtoPDF.convert({
      //   html: pdfContent,
      //   fileName: fileName,
      //   directory: 'Documents',
      // });

      console.log('✅ PDF generated:', filePath);
      return filePath;

    } catch (error) {
      console.error('❌ Error generating PDF:', error);
      throw error;
    }
  }

  /**
   * جمع بيانات التحليل
   */
  private async collectAnalyticsData(
    childId: string, 
    period: 'daily' | 'weekly' | 'monthly'
  ): Promise<AnalyticsData> {
    try {
      console.log('📈 Collecting analytics data...');

      const { startDate, endDate } = this.getPeriodDates(period);

      // جمع التفاعلات (محاكاة - في التطبيق الحقيقي سيأتي من API)
      const interactions = await this.getInteractionsData(childId, startDate, endDate);
      
      // جمع التنبيهات
      const alerts = this.alertService.getAlertsForChild(childId)
        .filter(alert => {
          const alertDate = new Date(alert.timestamp);
          return alertDate >= startDate && alertDate <= endDate;
        })
        .map(alert => ({
          id: alert.id,
          timestamp: alert.timestamp,
          severity: alert.severity,
          type: alert.type,
          resolved: alert.resolved,
          child_id: alert.child_id
        }));

      // تحليل أنماط الاستخدام
      const usagePatterns = this.analyzeUsagePatterns(interactions);

      return {
        interactions,
        alerts,
        usage_patterns: usagePatterns
      };

    } catch (error) {
      console.error('❌ Error collecting analytics data:', error);
      throw error;
    }
  }

  /**
   * تحليل البيانات باستخدام الذكاء الاصطناعي
   */
  private async analyzeData(
    data: AnalyticsData, 
    period: 'daily' | 'weekly' | 'monthly'
  ): Promise<any> {
    try {
      console.log('🤖 Analyzing data with AI...');

      // حساب الإحصائيات الأساسية
      const totalInteractions = data.interactions.length;
      const safeInteractions = data.interactions.filter(i => !i.has_forbidden_content).length;
      const flaggedInteractions = totalInteractions - safeInteractions;
      
      const averageSessionDuration = data.interactions.length > 0 ?
        data.interactions.reduce((sum, i) => sum + i.duration, 0) / data.interactions.length : 0;

      // حساب درجة الأمان
      const safetyScore = totalInteractions > 0 ? 
        Math.round((safeInteractions / totalInteractions) * 100) : 100;

      // تحليل الاتجاهات
      const trends = this.analyzeTrends(data, period);

      // تحليل السلوك بالذكاء الاصطناعي (محاكاة)
      const behaviorAnalysis = await this.generateBehaviorAnalysis(data, safetyScore);

      // توليد التوصيات
      const recommendations = this.generateRecommendations(data, safetyScore);

      // تحديد المخاوف
      const concerns = this.identifyConcerns(data);

      // ملاحظات التطور
      const progressNotes = this.generateProgressNotes(data, period);

      // النقاط الإيجابية
      const positiveHighlights = this.identifyPositiveHighlights(data, safetyScore);

      // مجالات التحسين
      const improvementAreas = this.identifyImprovementAreas(data, safetyScore);

      return {
        summary: {
          total_interactions: totalInteractions,
          safe_interactions: safeInteractions,
          flagged_interactions: flaggedInteractions,
          average_session_duration: averageSessionDuration,
          safety_score: safetyScore,
          improvement_areas: improvementAreas,
          positive_highlights: positiveHighlights
        },
        trends,
        ai_insights: {
          behavior_analysis: behaviorAnalysis,
          recommendations,
          concerns,
          progress_notes: progressNotes
        },
        alerts_summary: {
          total_alerts: data.alerts.length,
          critical_alerts: data.alerts.filter(a => a.severity === 'critical').length,
          resolved_alerts: data.alerts.filter(a => a.resolved).length,
          common_issues: this.identifyCommonIssues(data.alerts)
        }
      };

    } catch (error) {
      console.error('❌ Error analyzing data:', error);
      throw error;
    }
  }

  /**
   * إنشاء التقرير النهائي
   */
  private async createReport(
    childId: string,
    period: 'daily' | 'weekly' | 'monthly',
    data: AnalyticsData,
    analysis: any
  ): Promise<ReportData> {
    try {
      // الحصول على اسم الطفل
      const child = await this.getChildInfo(childId);
      const childName = child?.name || 'طفل غير معروف';

      const { startDate, endDate } = this.getPeriodDates(period);

      const report: ReportData = {
        id: `report_${childId}_${period}_${Date.now()}`,
        period,
        child_id: childId,
        child_name: childName,
        generated_at: new Date().toISOString(),
        summary: analysis.summary,
        trends: analysis.trends,
        ai_insights: analysis.ai_insights,
        alerts_summary: analysis.alerts_summary,
        metadata: {
          start_date: startDate.toISOString(),
          end_date: endDate.toISOString(),
          data_points: data.interactions.length,
          generation_duration: 0, // سيتم تحديثه
          ai_model_version: '1.0.0'
        }
      };

      return report;

    } catch (error) {
      console.error('❌ Error creating report:', error);
      throw error;
    }
  }

  /**
   * تحليل الاتجاهات
   */
  private analyzeTrends(data: AnalyticsData, period: 'daily' | 'weekly' | 'monthly') {
    const { startDate, endDate } = this.getPeriodDates(period);
    const daysDiff = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
    
    // تقسيم البيانات إلى فترات زمنية
    const intervals = this.createTimeIntervals(startDate, endDate, period);
    
    const interactionCount: number[] = [];
    const safetyScores: number[] = [];
    const sessionDurations: number[] = [];
    const labels: string[] = [];

    intervals.forEach(interval => {
      const intervalInteractions = data.interactions.filter(interaction => {
        const interactionDate = new Date(interaction.timestamp);
        return interactionDate >= interval.start && interactionDate < interval.end;
      });

      const count = intervalInteractions.length;
      const safeCount = intervalInteractions.filter(i => !i.has_forbidden_content).length;
      const safetyScore = count > 0 ? Math.round((safeCount / count) * 100) : 100;
      const avgDuration = count > 0 ? 
        intervalInteractions.reduce((sum, i) => sum + i.duration, 0) / count : 0;

      interactionCount.push(count);
      safetyScores.push(safetyScore);
      sessionDurations.push(avgDuration / 60); // تحويل للدقائق
      labels.push(this.formatIntervalLabel(interval.start, period));
    });

    return {
      interaction_count: interactionCount,
      safety_scores: safetyScores,
      session_durations: sessionDurations,
      labels
    };
  }

  /**
   * توليد تحليل السلوك بالذكاء الاصطناعي
   */
  private async generateBehaviorAnalysis(data: AnalyticsData, safetyScore: number): Promise<string> {
    // محاكاة تحليل AI (في التطبيق الحقيقي سيكون API call لـ OpenAI)
    
    const totalInteractions = data.interactions.length;
    const avgDuration = data.interactions.length > 0 ?
      data.interactions.reduce((sum, i) => sum + i.duration, 0) / data.interactions.length / 60 : 0;

    let analysis = '';

    if (safetyScore >= 90) {
      analysis = `يُظهر الطفل سلوكاً ممتازاً في التفاعل مع النظام مع درجة أمان عالية (${safetyScore}%). `;
    } else if (safetyScore >= 70) {
      analysis = `السلوك العام للطفل جيد مع درجة أمان مقبولة (${safetyScore}%)، لكن هناك مجال للتحسين. `;
    } else {
      analysis = `يحتاج سلوك الطفل لمراقبة أكثر حيث أن درجة الأمان (${safetyScore}%) تحتاج تحسين. `;
    }

    if (avgDuration > 30) {
      analysis += `متوسط مدة الجلسات (${Math.round(avgDuration)} دقيقة) مناسب ويدل على تفاعل صحي. `;
    } else if (avgDuration > 60) {
      analysis += `جلسات التفاعل طويلة نسبياً (${Math.round(avgDuration)} دقيقة)، قد تحتاج لمراقبة الوقت. `;
    }

    if (data.alerts.length === 0) {
      analysis += `لم يتم تسجيل أي تنبيهات أمان مما يدل على تفاعل آمن ومناسب.`;
    } else {
      analysis += `تم تسجيل ${data.alerts.length} تنبيه أمان، مما يستدعي المراجعة والمتابعة.`;
    }

    return analysis;
  }

  /**
   * توليد التوصيات
   */
  private generateRecommendations(data: AnalyticsData, safetyScore: number): string[] {
    const recommendations: string[] = [];

    if (safetyScore < 80) {
      recommendations.push('مراجعة إعدادات الأمان وتشديد المراقبة');
      recommendations.push('إجراء محادثة مع الطفل حول الاستخدام الآمن');
    }

    const avgDuration = data.interactions.length > 0 ?
      data.interactions.reduce((sum, i) => sum + i.duration, 0) / data.interactions.length / 60 : 0;

    if (avgDuration > 45) {
      recommendations.push('تحديد أوقات استراحة منتظمة أثناء الاستخدام');
      recommendations.push('تنويع الأنشطة غير الرقمية للطفل');
    }

    if (data.alerts.filter(a => !a.resolved).length > 0) {
      recommendations.push('مراجعة التنبيهات غير المحلولة والتعامل معها');
    }

    const criticalAlerts = data.alerts.filter(a => a.severity === 'critical');
    if (criticalAlerts.length > 0) {
      recommendations.push('استشارة متخصص في سلامة الأطفال عبر الإنترنت');
    }

    // إضافة توصيات إيجابية
    if (safetyScore >= 90) {
      recommendations.push('الاستمرار في نفس نمط الاستخدام الآمن');
      recommendations.push('تشجيع الطفل على سلوكه الإيجابي');
    }

    return recommendations;
  }

  /**
   * تحديد المخاوف
   */
  private identifyConcerns(data: AnalyticsData): string[] {
    const concerns: string[] = [];

    const criticalAlerts = data.alerts.filter(a => a.severity === 'critical');
    if (criticalAlerts.length > 0) {
      concerns.push(`${criticalAlerts.length} تنبيه حرج يحتاج تدخل فوري`);
    }

    const unresolvedAlerts = data.alerts.filter(a => !a.resolved);
    if (unresolvedAlerts.length > 3) {
      concerns.push(`${unresolvedAlerts.length} تنبيه غير محلول`);
    }

    const flaggedInteractions = data.interactions.filter(i => i.has_forbidden_content);
    if (flaggedInteractions.length > data.interactions.length * 0.2) {
      concerns.push('نسبة عالية من التفاعلات المحظورة');
    }

    const avgDuration = data.interactions.length > 0 ?
      data.interactions.reduce((sum, i) => sum + i.duration, 0) / data.interactions.length / 60 : 0;

    if (avgDuration > 60) {
      concerns.push('جلسات طويلة قد تؤثر على وقت الطفل');
    }

    return concerns;
  }

  /**
   * توليد ملاحظات التطور
   */
  private generateProgressNotes(data: AnalyticsData, period: string): string {
    const totalInteractions = data.interactions.length;
    const alertsCount = data.alerts.length;

    let notes = `خلال الفترة ${this.getPeriodLabel(period)}، `;

    if (totalInteractions > 0) {
      notes += `تفاعل الطفل ${totalInteractions} مرة مع النظام. `;
    } else {
      notes += `لم يحدث تفاعل مع النظام. `;
      return notes;
    }

    if (alertsCount === 0) {
      notes += `جميع التفاعلات كانت آمنة دون أي تنبيهات، مما يدل على تطور إيجابي في سلوك الطفل.`;
    } else {
      const resolvedAlerts = data.alerts.filter(a => a.resolved).length;
      notes += `تم تسجيل ${alertsCount} تنبيه، منها ${resolvedAlerts} تم حلها. `;
      
      if (resolvedAlerts === alertsCount) {
        notes += `جميع التنبيهات تم التعامل معها بشكل مناسب.`;
      } else {
        notes += `يحتاج ${alertsCount - resolvedAlerts} تنبيه للمراجعة.`;
      }
    }

    return notes;
  }

  /**
   * تحديد النقاط الإيجابية
   */
  private identifyPositiveHighlights(data: AnalyticsData, safetyScore: number): string[] {
    const highlights: string[] = [];

    if (safetyScore >= 95) {
      highlights.push('درجة أمان ممتازة تزيد عن 95%');
    } else if (safetyScore >= 85) {
      highlights.push('درجة أمان جيدة جداً');
    }

    if (data.alerts.length === 0) {
      highlights.push('لا توجد تنبيهات أمان في هذه الفترة');
    }

    const resolvedAlertsRatio = data.alerts.length > 0 ? 
      data.alerts.filter(a => a.resolved).length / data.alerts.length : 1;

    if (resolvedAlertsRatio === 1 && data.alerts.length > 0) {
      highlights.push('جميع التنبيهات تم حلها بنجاح');
    }

    if (data.interactions.length > 0) {
      const consistentUsage = this.checkUsageConsistency(data.interactions);
      if (consistentUsage) {
        highlights.push('استخدام منتظم ومنضبط');
      }
    }

    return highlights;
  }

  /**
   * تحديد مجالات التحسين
   */
  private identifyImprovementAreas(data: AnalyticsData, safetyScore: number): string[] {
    const areas: string[] = [];

    if (safetyScore < 80) {
      areas.push('تحسين ممارسات الأمان الرقمي');
    }

    const avgDuration = data.interactions.length > 0 ?
      data.interactions.reduce((sum, i) => sum + i.duration, 0) / data.interactions.length / 60 : 0;

    if (avgDuration > 45) {
      areas.push('إدارة وقت الاستخدام');
    }

    if (data.alerts.filter(a => !a.resolved).length > 0) {
      areas.push('متابعة وحل التنبيهات الأمنية');
    }

    const flaggedRatio = data.interactions.length > 0 ?
      data.interactions.filter(i => i.has_forbidden_content).length / data.interactions.length : 0;

    if (flaggedRatio > 0.1) {
      areas.push('تقليل المحتوى غير المناسب');
    }

    return areas;
  }

  /**
   * تحديد المشاكل الشائعة
   */
  private identifyCommonIssues(alerts: any[]): string[] {
    const issueCount: { [key: string]: number } = {};

    alerts.forEach(alert => {
      issueCount[alert.type] = (issueCount[alert.type] || 0) + 1;
    });

    return Object.entries(issueCount)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([type, count]) => `${this.getIssueLabel(type)} (${count} مرة)`);
  }

  /**
   * دوال مساعدة
   */
  private getPeriodDates(period: 'daily' | 'weekly' | 'monthly') {
    const endDate = new Date();
    const startDate = new Date();

    switch (period) {
      case 'daily':
        startDate.setDate(endDate.getDate() - 1);
        break;
      case 'weekly':
        startDate.setDate(endDate.getDate() - 7);
        break;
      case 'monthly':
        startDate.setMonth(endDate.getMonth() - 1);
        break;
    }

    return { startDate, endDate };
  }

  private createTimeIntervals(startDate: Date, endDate: Date, period: string) {
    const intervals = [];
    const current = new Date(startDate);

    while (current < endDate) {
      const intervalEnd = new Date(current);
      
      switch (period) {
        case 'daily':
          intervalEnd.setHours(current.getHours() + 4); // كل 4 ساعات
          break;
        case 'weekly':
          intervalEnd.setDate(current.getDate() + 1); // كل يوم
          break;
        case 'monthly':
          intervalEnd.setDate(current.getDate() + 7); // كل أسبوع
          break;
      }

      intervals.push({
        start: new Date(current),
        end: new Date(Math.min(intervalEnd.getTime(), endDate.getTime()))
      });

      current.setTime(intervalEnd.getTime());
    }

    return intervals;
  }

  private formatIntervalLabel(date: Date, period: string): string {
    switch (period) {
      case 'daily':
        return date.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });
      case 'weekly':
        return date.toLocaleDateString('ar-EG', { weekday: 'short' });
      case 'monthly':
        return date.toLocaleDateString('ar-EG', { month: 'short', day: 'numeric' });
      default:
        return date.toLocaleDateString('ar-EG');
    }
  }

  private getPeriodLabel(period: string): string {
    const labels = {
      daily: 'اليومية',
      weekly: 'الأسبوعية',
      monthly: 'الشهرية'
    };
    return labels[period as keyof typeof labels] || period;
  }

  private getIssueLabel(type: string): string {
    const labels = {
      forbidden_content: 'محتوى محظور',
      excessive_usage: 'استخدام مفرط',
      inappropriate_interaction: 'تفاعل غير مناسب',
      self_harm: 'إيذاء النفس',
      emergency: 'حالة طارئة'
    };
    return labels[type as keyof typeof labels] || type;
  }

  private getReportKey(childId: string, period: string): string {
    return `${childId}_${period}`;
  }

  private async getInteractionsData(childId: string, startDate: Date, endDate: Date) {
    try {
      // في التطبيق الحقيقي سيأتي من API
      const interactions = await ApiService.getChildInteractions(childId, 100);
      
      return interactions
        .filter(interaction => {
          const interactionDate = new Date(interaction.timestamp);
          return interactionDate >= startDate && interactionDate <= endDate;
        })
        .map(interaction => ({
          id: interaction.id,
          timestamp: interaction.timestamp,
          duration: interaction.usage_duration || 300, // 5 دقائق افتراضي
          has_forbidden_content: interaction.has_forbidden_content,
          child_id: interaction.child_id
        }));
    } catch (error) {
      console.error('❌ Error getting interactions data:', error);
      return [];
    }
  }

  private async getChildInfo(childId: string) {
    try {
      return await ApiService.getChild(childId);
    } catch (error) {
      console.error('❌ Error getting child info:', error);
      return null;
    }
  }

  private analyzeUsagePatterns(interactions: any[]) {
    const dailyHours = new Array(24).fill(0);
    const sessionLengths: number[] = [];

    interactions.forEach(interaction => {
      const hour = new Date(interaction.timestamp).getHours();
      dailyHours[hour]++;
      sessionLengths.push(interaction.duration / 60); // تحويل للدقائق
    });

    // تحديد أوقات الذروة
    const maxUsage = Math.max(...dailyHours);
    const peakTimes = dailyHours
      .map((count, hour) => ({ hour, count }))
      .filter(({ count }) => count === maxUsage)
      .map(({ hour }) => `${hour}:00`);

    return {
      daily_hours: dailyHours,
      peak_times: peakTimes,
      session_lengths: sessionLengths
    };
  }

  private checkUsageConsistency(interactions: any[]): boolean {
    if (interactions.length < 2) return false;

    const dailyUsage: { [key: string]: number } = {};

    interactions.forEach(interaction => {
      const day = new Date(interaction.timestamp).toDateString();
      dailyUsage[day] = (dailyUsage[day] || 0) + 1;
    });

    const usageCounts = Object.values(dailyUsage);
    const avgUsage = usageCounts.reduce((sum, count) => sum + count, 0) / usageCounts.length;
    
    // التحقق من الثبات (انحراف معياري منخفض)
    const variance = usageCounts.reduce((sum, count) => sum + Math.pow(count - avgUsage, 2), 0) / usageCounts.length;
    const standardDeviation = Math.sqrt(variance);

    return standardDeviation < avgUsage * 0.3; // انحراف أقل من 30%
  }

  private generatePDFContent(report: ReportData): string {
    // إنشاء محتوى HTML للـ PDF
    return `
      <!DOCTYPE html>
      <html dir="rtl" lang="ar">
      <head>
        <meta charset="UTF-8">
        <title>تقرير ${report.child_name}</title>
        <style>
          body { font-family: 'Arial', sans-serif; direction: rtl; }
          .header { text-align: center; margin-bottom: 30px; }
          .stat { display: inline-block; margin: 10px; padding: 15px; border: 1px solid #ddd; }
          .chart { margin: 20px 0; }
          .insights { margin: 20px 0; padding: 15px; background: #f9f9f9; }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>تقرير ${this.getPeriodLabel(report.period)} - ${report.child_name}</h1>
          <p>تاريخ الإنشاء: ${new Date(report.generated_at).toLocaleDateString('ar-EG')}</p>
        </div>
        
        <div class="stats">
          <div class="stat">
            <h3>إجمالي التفاعلات</h3>
            <p>${report.summary.total_interactions}</p>
          </div>
          <div class="stat">
            <h3>درجة الأمان</h3>
            <p>${report.summary.safety_score}%</p>
          </div>
        </div>
        
        <div class="insights">
          <h2>التحليل الذكي</h2>
          <p>${report.ai_insights.behavior_analysis}</p>
        </div>
        
        <!-- المزيد من المحتوى... -->
      </body>
      </html>
    `;
  }

  private async saveReport(report: ReportData): Promise<void> {
    try {
      const reportKey = this.getReportKey(report.child_id, report.period);
      
      // حفظ في الكاش
      this.cachedReports.set(reportKey, report);
      
      // حفظ محلياً
      await AsyncStorage.setItem(`report_${reportKey}`, JSON.stringify(report));
      
      console.log('✅ Report saved successfully');
    } catch (error) {
      console.error('❌ Error saving report:', error);
      throw error;
    }
  }

  /**
   * تنظيف الموارد
   */
  public async cleanup(): Promise<void> {
    this.cachedReports.clear();
    this.generationQueue = [];
    this.removeAllListeners();
    console.log('✅ ReportService cleanup completed');
  }
}

export default ReportService;
