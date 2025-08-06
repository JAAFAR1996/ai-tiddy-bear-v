/**
 * Reports Screen - شاشة التقارير الذكية والتحليلات
 * 
 * Features:
 * - AI-generated daily/weekly reports
 * - Interactive charts and visualizations
 * - Child behavior analysis
 * - Safety trends and insights
 * - Downloadable PDF reports
 * - Arabic RTL support
 * 
 * @version 1.0.0
 * @since 2025-08-04
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
  Alert,
  Dimensions,
  Share,
} from 'react-native';
import { Child, SafetyAlert } from '../types';
import { ApiService } from '../services/api';
import { ReportService, ReportData } from '../services/ReportService';

const { width: screenWidth } = Dimensions.get('window');

interface ReportsScreenProps {
  children: Child[];
  onNavigateBack: () => void;
}

interface StatCardProps {
  title: string;
  value: string | number;
  icon: string;
  color: string;
  trend?: 'up' | 'down' | 'stable';
  subtitle?: string;
}

const StatCard: React.FC<StatCardProps> = ({ 
  title, 
  value, 
  icon, 
  color, 
  trend, 
  subtitle 
}) => {
  const getTrendIcon = () => {
    switch (trend) {
      case 'up': return '📈';
      case 'down': return '📉';
      case 'stable': return '➡️';
      default: return '';
    }
  };

  return (
    <View style={[styles.statCard, { borderTopColor: color }]}>
      <View style={styles.statHeader}>
        <Text style={styles.statIcon}>{icon}</Text>
        <Text style={styles.statTitle}>{title}</Text>
      </View>
      
      <View style={styles.statContent}>
        <Text style={[styles.statValue, { color }]}>{value}</Text>
        {trend && (
          <Text style={styles.statTrend}>
            {getTrendIcon()}
          </Text>
        )}
      </View>
      
      {subtitle && (
        <Text style={styles.statSubtitle}>{subtitle}</Text>
      )}
    </View>
  );
};

interface ChartData {
  data: number[];
  labels: string[];
  title: string;
}

const SimpleLineChart: React.FC<ChartData> = ({ data, labels, title }) => {
  const maxValue = Math.max(...data);
  const minValue = Math.min(...data);
  const range = maxValue - minValue || 1;

  return (
    <View style={styles.chartContainer}>
      <Text style={styles.chartTitle}>{title}</Text>
      
      <View style={styles.chart}>
        <View style={styles.chartArea}>
          {data.map((value, index) => {
            const height = ((value - minValue) / range) * 100;
            return (
              <View key={index} style={styles.chartColumn}>
                <View 
                  style={[
                    styles.chartBar, 
                    { 
                      height: `${height}%`,
                      backgroundColor: height > 70 ? '#27AE60' : 
                                     height > 40 ? '#F39C12' : '#E74C3C'
                    }
                  ]} 
                />
                <Text style={styles.chartLabel}>
                  {labels[index]}
                </Text>
              </View>
            );
          })}
        </View>
        
        <View style={styles.chartLegend}>
          <Text style={styles.chartMaxValue}>{maxValue.toFixed(1)}</Text>
          <Text style={styles.chartMinValue}>{minValue.toFixed(1)}</Text>
        </View>
      </View>
    </View>
  );
};

const ReportsScreen: React.FC<ReportsScreenProps> = ({ 
  children, 
  onNavigateBack 
}) => {
  const [reports, setReports] = useState<ReportData[]>([]);
  const [selectedChild, setSelectedChild] = useState<string>('');
  const [selectedPeriod, setSelectedPeriod] = useState<'daily' | 'weekly' | 'monthly'>('weekly');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [generating, setGenerating] = useState(false);

  const reportService = ReportService.getInstance();

  useEffect(() => {
    if (children.length > 0 && !selectedChild) {
      setSelectedChild(children[0].id);
    }
    loadReports();
  }, [children, selectedChild, selectedPeriod]);

  const loadReports = async () => {
    try {
      setLoading(true);
      
      if (!selectedChild) return;
      
      const reportData = await reportService.getReport(selectedChild, selectedPeriod);
      setReports(reportData ? [reportData] : []);
      
    } catch (error) {
      console.error('❌ Error loading reports:', error);
      Alert.alert('خطأ', 'فشل في تحميل التقارير');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadReports();
    setRefreshing(false);
  };

  const handleGenerateReport = async () => {
    if (!selectedChild) return;

    try {
      setGenerating(true);
      
      Alert.alert(
        'إنشاء تقرير جديد',
        `هل تريد إنشاء تقرير ${selectedPeriod === 'daily' ? 'يومي' : selectedPeriod === 'weekly' ? 'أسبوعي' : 'شهري'} جديد؟`,
        [
          { text: 'إلغاء', style: 'cancel' },
          {
            text: 'إنشاء',
            onPress: async () => {
              try {
                await reportService.generateReport(selectedChild, selectedPeriod);
                await loadReports();
                Alert.alert('نجح', 'تم إنشاء التقرير بنجاح');
              } catch (error) {
                Alert.alert('خطأ', 'فشل في إنشاء التقرير');
              }
            }
          }
        ]
      );
    } catch (error) {
      console.error('❌ Error generating report:', error);
      Alert.alert('خطأ', 'فشل في إنشاء التقرير');
    } finally {
      setGenerating(false);
    }
  };

  const handleShareReport = async (report: ReportData) => {
    try {
      const pdfPath = await reportService.generatePDF(report);
      
      await Share.share({
        title: `تقرير ${report.child_name} - ${selectedPeriod}`,
        message: `تقرير سلامة وتطور ${report.child_name}`,
        url: pdfPath,
      });
    } catch (error) {
      console.error('❌ Error sharing report:', error);
      Alert.alert('خطأ', 'فشل في مشاركة التقرير');
    }
  };

  const currentReport = reports.length > 0 ? reports[0] : null;
  const selectedChildData = children.find(c => c.id === selectedChild);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ar-EG', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const getPeriodLabel = (period: string) => {
    const labels = {
      daily: 'يومي',
      weekly: 'أسبوعي',
      monthly: 'شهري'
    };
    return labels[period as keyof typeof labels] || period;
  };

  const getSafetyScoreColor = (score: number) => {
    if (score >= 90) return '#27AE60';
    if (score >= 70) return '#F39C12';
    if (score >= 50) return '#E67E22';
    return '#E74C3C';
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={onNavigateBack} style={styles.backButton}>
          <Text style={styles.backIcon}>◀️</Text>
        </TouchableOpacity>
        
        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle}>📊 التقارير الذكية</Text>
          <Text style={styles.headerSubtitle}>تحليل سلوك وأمان الطفل</Text>
        </View>
        
        <TouchableOpacity 
          onPress={handleGenerateReport}
          style={styles.generateButton}
          disabled={generating}
        >
          {generating ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.generateButtonText}>📋 إنشاء</Text>
          )}
        </TouchableOpacity>
      </View>

      <ScrollView 
        style={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            colors={['#3498DB']}
          />
        }
      >
        {/* Controls */}
        <View style={styles.controls}>
          {/* Child Selector */}
          <View style={styles.controlGroup}>
            <Text style={styles.controlLabel}>👶 اختر الطفل:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              {children.map(child => (
                <TouchableOpacity
                  key={child.id}
                  style={[
                    styles.childTab,
                    selectedChild === child.id && styles.activeChildTab
                  ]}
                  onPress={() => setSelectedChild(child.id)}
                >
                  <Text style={[
                    styles.childTabText,
                    selectedChild === child.id && styles.activeChildTabText
                  ]}>
                    {child.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          {/* Period Selector */}
          <View style={styles.controlGroup}>
            <Text style={styles.controlLabel}>📅 الفترة الزمنية:</Text>
            <View style={styles.periodTabs}>
              {(['daily', 'weekly', 'monthly'] as const).map(period => (
                <TouchableOpacity
                  key={period}
                  style={[
                    styles.periodTab,
                    selectedPeriod === period && styles.activePeriodTab
                  ]}
                  onPress={() => setSelectedPeriod(period)}
                >
                  <Text style={[
                    styles.periodTabText,
                    selectedPeriod === period && styles.activePeriodTabText
                  ]}>
                    {getPeriodLabel(period)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </View>

        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#3498DB" />
            <Text style={styles.loadingText}>جاري تحميل التقارير...</Text>
          </View>
        ) : currentReport ? (
          <>
            {/* Report Header */}
            <View style={styles.reportHeader}>
              <Text style={styles.reportTitle}>
                📊 تقرير {getPeriodLabel(selectedPeriod)} - {currentReport.child_name}
              </Text>
              <Text style={styles.reportDate}>
                تم الإنشاء: {formatDate(currentReport.generated_at)}
              </Text>
              
              <TouchableOpacity
                style={styles.shareButton}
                onPress={() => handleShareReport(currentReport)}
              >
                <Text style={styles.shareButtonText}>📤 مشاركة التقرير</Text>
              </TouchableOpacity>
            </View>

            {/* Statistics Cards */}
            <View style={styles.statsGrid}>
              <StatCard
                title="التفاعلات الإجمالية"
                value={currentReport.summary.total_interactions}
                icon="💬"
                color="#3498DB"
                subtitle={`${Math.round((currentReport.summary.safe_interactions / currentReport.summary.total_interactions) * 100)}% آمنة`}
              />
              
              <StatCard
                title="درجة الأمان"
                value={`${currentReport.summary.safety_score}%`}
                icon="🛡️"
                color={getSafetyScoreColor(currentReport.summary.safety_score)}
                trend={currentReport.summary.safety_score >= 80 ? 'up' : 
                       currentReport.summary.safety_score >= 60 ? 'stable' : 'down'}
              />
              
              <StatCard
                title="متوسط الجلسة"
                value={`${Math.round(currentReport.summary.average_session_duration / 60)} دقيقة`}
                icon="⏱️"
                color="#9B59B6"
              />
              
              <StatCard
                title="التنبيهات"
                value={currentReport.alerts_summary.total_alerts}
                icon="🚨"
                color={currentReport.alerts_summary.critical_alerts > 0 ? '#E74C3C' : '#27AE60'}
                subtitle={`${currentReport.alerts_summary.resolved_alerts} محلول`}
              />
            </View>

            {/* Charts */}
            {currentReport.trends.interaction_count.length > 0 && (
              <SimpleLineChart
                data={currentReport.trends.interaction_count}
                labels={currentReport.trends.labels}
                title="📈 اتجاه التفاعلات"
              />
            )}

            {currentReport.trends.safety_scores.length > 0 && (
              <SimpleLineChart
                data={currentReport.trends.safety_scores}
                labels={currentReport.trends.labels}
                title="🛡️ تطور درجة الأمان"
              />
            )}

            {/* AI Insights */}
            <View style={styles.insightsSection}>
              <Text style={styles.sectionTitle}>🤖 التحليل الذكي</Text>
              
              <View style={styles.insightCard}>
                <Text style={styles.insightTitle}>📊 تحليل السلوك</Text>
                <Text style={styles.insightText}>
                  {currentReport.ai_insights.behavior_analysis}
                </Text>
              </View>

              {currentReport.ai_insights.recommendations.length > 0 && (
                <View style={styles.insightCard}>
                  <Text style={styles.insightTitle}>💡 التوصيات</Text>
                  {currentReport.ai_insights.recommendations.map((rec: string, index: number) => (
                    <Text key={index} style={styles.bulletPoint}>
                      • {rec}
                    </Text>
                  ))}
                </View>
              )}

              {currentReport.ai_insights.concerns.length > 0 && (
                <View style={[styles.insightCard, styles.concernCard]}>
                  <Text style={[styles.insightTitle, styles.concernTitle]}>
                    ⚠️ نقاط تحتاج انتباه
                  </Text>
                  {currentReport.ai_insights.concerns.map((concern: string, index: number) => (
                    <Text key={index} style={styles.bulletPoint}>
                      • {concern}
                    </Text>
                  ))}
                </View>
              )}

              {currentReport.ai_insights.progress_notes && (
                <View style={styles.insightCard}>
                  <Text style={styles.insightTitle}>📝 ملاحظات التطور</Text>
                  <Text style={styles.insightText}>
                    {currentReport.ai_insights.progress_notes}
                  </Text>
                </View>
              )}
            </View>

            {/* Highlights */}
            {currentReport.summary.positive_highlights.length > 0 && (
              <View style={styles.highlightsSection}>
                <Text style={styles.sectionTitle}>✨ الإنجازات الإيجابية</Text>
                {currentReport.summary.positive_highlights.map((highlight: string, index: number) => (
                  <View key={index} style={styles.highlightItem}>
                    <Text style={styles.highlightText}>🎉 {highlight}</Text>
                  </View>
                ))}
              </View>
            )}

            {/* Improvement Areas */}
            {currentReport.summary.improvement_areas.length > 0 && (
              <View style={styles.improvementSection}>
                <Text style={styles.sectionTitle}>🎯 مجالات التحسين</Text>
                {currentReport.summary.improvement_areas.map((area: string, index: number) => (
                  <View key={index} style={styles.improvementItem}>
                    <Text style={styles.improvementText}>🔄 {area}</Text>
                  </View>
                ))}
              </View>
            )}

          </>
        ) : (
          <View style={styles.emptyState}>
            <Text style={styles.emptyStateIcon}>📊</Text>
            <Text style={styles.emptyStateTitle}>لا توجد تقارير</Text>
            <Text style={styles.emptyStateText}>
              {selectedChildData ? 
                `لم يتم إنشاء تقارير لـ ${selectedChildData.name} بعد` :
                'اختر طفلاً لعرض التقارير'
              }
            </Text>
            <TouchableOpacity
              style={styles.emptyStateButton}
              onPress={handleGenerateReport}
              disabled={generating}
            >
              <Text style={styles.emptyStateButtonText}>
                📋 إنشاء أول تقرير
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8F9FA',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 20,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  backButton: {
    padding: 8,
  },
  backIcon: {
    fontSize: 20,
  },
  headerCenter: {
    flex: 1,
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#2C3E50',
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#7F8C8D',
    marginTop: 2,
  },
  generateButton: {
    backgroundColor: '#3498DB',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
  },
  generateButtonText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  content: {
    flex: 1,
  },
  controls: {
    backgroundColor: '#FFFFFF',
    padding: 15,
    marginBottom: 10,
  },
  controlGroup: {
    marginBottom: 15,
  },
  controlLabel: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#2C3E50',
    marginBottom: 8,
    textAlign: 'right',
  },
  childTab: {
    backgroundColor: '#ECF0F1',
    paddingHorizontal: 15,
    paddingVertical: 8,
    borderRadius: 20,
    marginHorizontal: 5,
  },
  activeChildTab: {
    backgroundColor: '#3498DB',
  },
  childTabText: {
    color: '#2C3E50',
    fontSize: 14,
  },
  activeChildTabText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
  periodTabs: {
    flexDirection: 'row',
    backgroundColor: '#ECF0F1',
    borderRadius: 8,
    padding: 4,
  },
  periodTab: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 6,
  },
  activePeriodTab: {
    backgroundColor: '#3498DB',
  },
  periodTabText: {
    color: '#2C3E50',
    fontSize: 14,
  },
  activePeriodTabText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
  loadingContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  loadingText: {
    marginTop: 15,
    fontSize: 16,
    color: '#7F8C8D',
  },
  reportHeader: {
    backgroundColor: '#FFFFFF',
    padding: 20,
    marginBottom: 15,
    alignItems: 'center',
  },
  reportTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2C3E50',
    textAlign: 'center',
    marginBottom: 5,
  },
  reportDate: {
    fontSize: 12,
    color: '#7F8C8D',
    marginBottom: 15,
  },
  shareButton: {
    backgroundColor: '#27AE60',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
  },
  shareButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 10,
    marginBottom: 15,
  },
  statCard: {
    width: (screenWidth - 40) / 2,
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 15,
    margin: 5,
    borderTopWidth: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  statHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  statIcon: {
    fontSize: 20,
    marginRight: 8,
  },
  statTitle: {
    fontSize: 12,
    color: '#7F8C8D',
    flex: 1,
    textAlign: 'right',
  },
  statContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  statValue: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  statTrend: {
    fontSize: 16,
  },
  statSubtitle: {
    fontSize: 10,
    color: '#95A5A6',
    marginTop: 5,
    textAlign: 'right',
  },
  chartContainer: {
    backgroundColor: '#FFFFFF',
    margin: 10,
    borderRadius: 12,
    padding: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  chartTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#2C3E50',
    textAlign: 'right',
    marginBottom: 15,
  },
  chart: {
    flexDirection: 'row',
    height: 120,
  },
  chartArea: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-around',
  },
  chartColumn: {
    flex: 1,
    alignItems: 'center',
  },
  chartBar: {
    width: 20,
    borderRadius: 2,
    marginBottom: 5,
  },
  chartLabel: {
    fontSize: 10,
    color: '#7F8C8D',
    textAlign: 'center',
  },
  chartLegend: {
    justifyContent: 'space-between',
    paddingLeft: 10,
    width: 40,
  },
  chartMaxValue: {
    fontSize: 10,
    color: '#7F8C8D',
  },
  chartMinValue: {
    fontSize: 10,
    color: '#7F8C8D',
  },
  insightsSection: {
    margin: 10,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2C3E50',
    textAlign: 'right',
    marginBottom: 15,
  },
  insightCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  concernCard: {
    borderLeftWidth: 4,
    borderLeftColor: '#E74C3C',
  },
  insightTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#2C3E50',
    textAlign: 'right',
    marginBottom: 8,
  },
  concernTitle: {
    color: '#E74C3C',
  },
  insightText: {
    fontSize: 14,
    color: '#5D6D7E',
    textAlign: 'right',
    lineHeight: 20,
  },
  bulletPoint: {
    fontSize: 14,
    color: '#5D6D7E',
    textAlign: 'right',
    marginBottom: 5,
    lineHeight: 20,
  },
  highlightsSection: {
    margin: 10,
  },
  highlightItem: {
    backgroundColor: 'rgba(39, 174, 96, 0.1)',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#27AE60',
  },
  highlightText: {
    fontSize: 14,
    color: '#27AE60',
    textAlign: 'right',
    fontWeight: '500',
  },
  improvementSection: {
    margin: 10,
  },
  improvementItem: {
    backgroundColor: 'rgba(52, 152, 219, 0.1)',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#3498DB',
  },
  improvementText: {
    fontSize: 14,
    color: '#3498DB',
    textAlign: 'right',
    fontWeight: '500',
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 80,
    paddingHorizontal: 40,
  },
  emptyStateIcon: {
    fontSize: 64,
    marginBottom: 20,
  },
  emptyStateTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#2C3E50',
    marginBottom: 10,
    textAlign: 'center',
  },
  emptyStateText: {
    fontSize: 14,
    color: '#7F8C8D',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 30,
  },
  emptyStateButton: {
    backgroundColor: '#3498DB',
    paddingHorizontal: 30,
    paddingVertical: 12,
    borderRadius: 8,
  },
  emptyStateButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
});

export default ReportsScreen;
