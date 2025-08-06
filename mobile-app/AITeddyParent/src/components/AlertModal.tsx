/**
 * Alert Modal - نافذة عرض التنبيهات التفاعلية
 * 
 * Features:
 * - Real-time alert display
 * - Priority-based styling and animations
 * - Quick action buttons
 * - Arabic RTL support
 * - COPPA-compliant information display
 * - Accessibility support
 * 
 * @version 1.0.0
 * @since 2025-08-04
 */

import React, { useState, useEffect } from 'react';
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Animated,
  Vibration,
  ScrollView,
  Alert as ReactNativeAlert,
  Dimensions,
  StatusBar,
} from 'react-native';
import { SafetyAlert } from '../types';

const { width: screenWidth, height: screenHeight } = Dimensions.get('window');

interface AlertModalProps {
  alerts: SafetyAlert[];
  visible: boolean;
  onClose: () => void;
  onResolveAlert: (alertId: string) => void;
  onViewDetails: (alert: SafetyAlert) => void;
  onEmergencyAction?: (alert: SafetyAlert) => void;
}

interface AlertCardProps {
  alert: SafetyAlert;
  onResolve: () => void;
  onViewDetails: () => void;
  onEmergencyAction?: () => void;
  isFirst: boolean;
}

const AlertCard: React.FC<AlertCardProps> = ({
  alert,
  onResolve,
  onViewDetails,
  onEmergencyAction,
  isFirst
}) => {
  const [slideAnim] = useState(new Animated.Value(isFirst ? 0 : 100));
  const [pulseAnim] = useState(new Animated.Value(1));

  useEffect(() => {
    // أنيميشن الدخول
    Animated.timing(slideAnim, {
      toValue: 0,
      duration: 300,
      useNativeDriver: true,
    }).start();

    // نبضة للتنبيهات الحرجة
    if (alert.severity === 'critical' || alert.requires_immediate_action) {
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.1,
            duration: 800,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 800,
            useNativeDriver: true,
          }),
        ])
      );
      pulse.start();

      return () => pulse.stop();
    }
  }, [alert.severity, alert.requires_immediate_action]);

  const getSeverityConfig = (severity: string) => {
    const configs = {
      low: {
        color: '#FFA500',
        backgroundColor: '#FFF4E6',
        borderColor: '#FFD700',
        icon: '🟡',
        label: 'منخفض'
      },
      medium: {
        color: '#FF8C00',
        backgroundColor: '#FFF2E6',
        borderColor: '#FF8C00',
        icon: '🟠',
        label: 'متوسط'
      },
      high: {
        color: '#FF4500',
        backgroundColor: '#FFEBE6',
        borderColor: '#FF4500',
        icon: '🔴',
        label: 'عالي'
      },
      critical: {
        color: '#DC143C',
        backgroundColor: '#FFE4E1',
        borderColor: '#DC143C',
        icon: '🚨',
        label: 'حرج'
      }
    };

    return configs[severity as keyof typeof configs] || configs.medium;
  };

  const getTypeConfig = (type: string) => {
    const configs = {
      forbidden_content: {
        icon: '🚫',
        label: 'محتوى محظور',
        description: 'تم اكتشاف محتوى غير مناسب للطفل'
      },
      self_harm: {
        icon: '⚠️',
        label: 'إيذاء النفس',
        description: 'مؤشرات على نية إيذاء النفس'
      },
      excessive_usage: {
        icon: '⏰',
        label: 'استخدام مفرط',
        description: 'تجاوز الحد المسموح للاستخدام'
      },
      inappropriate_interaction: {
        icon: '💬',
        label: 'تفاعل غير مناسب',
        description: 'تفاعل قد يكون ضاراً أو غير مناسب'
      },
      emergency: {
        icon: '🚨',
        label: 'حالة طارئة',
        description: 'حالة تتطلب تدخلاً فورياً'
      }
    };

    return configs[type as keyof typeof configs] || configs.inappropriate_interaction;
  };

  const severityConfig = getSeverityConfig(alert.severity);
  const typeConfig = getTypeConfig(alert.type);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMinutes / 60);

    if (diffMinutes < 1) return 'الآن';
    if (diffMinutes < 60) return `منذ ${diffMinutes} دقيقة`;
    if (diffHours < 24) return `منذ ${diffHours} ساعة`;
    
    return date.toLocaleDateString('ar-EG', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <Animated.View
      style={[
        styles.alertCard,
        {
          backgroundColor: severityConfig.backgroundColor,
          borderColor: severityConfig.borderColor,
          transform: [
            { translateY: slideAnim },
            { scale: pulseAnim }
          ]
        }
      ]}
    >
      {/* Header */}
      <View style={styles.alertHeader}>
        <View style={styles.alertHeaderLeft}>
          <Text style={styles.typeIcon}>{typeConfig.icon}</Text>
          <View>
            <Text style={[styles.alertTitle, { color: severityConfig.color }]}>
              {typeConfig.label}
            </Text>
            <Text style={styles.alertTime}>
              {formatTime(alert.timestamp)}
            </Text>
          </View>
        </View>
        
        <View style={styles.alertHeaderRight}>
          <View style={[styles.severityBadge, { backgroundColor: severityConfig.color }]}>
            <Text style={styles.severityText}>
              {severityConfig.icon} {severityConfig.label}
            </Text>
          </View>
        </View>
      </View>

      {/* Content */}
      <View style={styles.alertContent}>
        <Text style={styles.alertDescription}>
          {typeConfig.description}
        </Text>
        
        <Text style={styles.alertMessage}>
          "{alert.message}"
        </Text>

        {alert.context && (
          <View style={styles.contextInfo}>
            {alert.context.interaction_duration && (
              <Text style={styles.contextText}>
                ⏱️ مدة التفاعل: {Math.round(alert.context.interaction_duration / 60)} دقيقة
              </Text>
            )}
            {alert.context.previous_warnings && alert.context.previous_warnings > 0 && (
              <Text style={styles.contextText}>
                ⚠️ تحذيرات سابقة: {alert.context.previous_warnings}
              </Text>
            )}
          </View>
        )}

        {alert.risk_score && alert.risk_score > 0 && (
          <View style={styles.riskIndicator}>
            <Text style={styles.riskText}>
              📊 درجة المخاطرة: {alert.risk_score}/100
            </Text>
            <View style={styles.riskBar}>
              <View 
                style={[
                  styles.riskBarFill,
                  { 
                    width: `${alert.risk_score}%`,
                    backgroundColor: alert.risk_score > 70 ? '#DC143C' : 
                                   alert.risk_score > 40 ? '#FF8C00' : '#32CD32'
                  }
                ]}
              />
            </View>
          </View>
        )}
      </View>

      {/* Actions */}
      <View style={styles.alertActions}>
        {alert.requires_immediate_action && onEmergencyAction && (
          <TouchableOpacity
            style={[styles.actionButton, styles.emergencyButton]}
            onPress={onEmergencyAction}
          >
            <Text style={styles.emergencyButtonText}>
              🚨 إجراء طارئ
            </Text>
          </TouchableOpacity>
        )}
        
        <TouchableOpacity
          style={[styles.actionButton, styles.detailsButton]}
          onPress={onViewDetails}
        >
          <Text style={styles.detailsButtonText}>
            📋 التفاصيل
          </Text>
        </TouchableOpacity>
        
        {!alert.resolved && (
          <TouchableOpacity
            style={[styles.actionButton, styles.resolveButton]}
            onPress={onResolve}
          >
            <Text style={styles.resolveButtonText}>
              ✅ تأكيد المراجعة
            </Text>
          </TouchableOpacity>
        )}
      </View>

      {alert.resolved && (
        <View style={styles.resolvedBadge}>
          <Text style={styles.resolvedText}>
            ✅ تم الحل {alert.resolved_at && `في ${formatTime(alert.resolved_at)}`}
          </Text>
          {alert.resolved_by && (
            <Text style={styles.resolvedByText}>
              بواسطة: {alert.resolved_by}
            </Text>
          )}
        </View>
      )}
    </Animated.View>
  );
};

const AlertModal: React.FC<AlertModalProps> = ({
  alerts,
  visible,
  onClose,
  onResolveAlert,
  onViewDetails,
  onEmergencyAction
}) => {
  const [fadeAnim] = useState(new Animated.Value(0));
  const [slideAnim] = useState(new Animated.Value(screenHeight));

  useEffect(() => {
    if (visible) {
      StatusBar.setBarStyle('light-content');
      
      // اهتزاز للتنبيهات الحرجة
      const criticalAlerts = alerts.filter(alert => 
        alert.severity === 'critical' || alert.requires_immediate_action
      );
      
      if (criticalAlerts.length > 0) {
        Vibration.vibrate([0, 500, 200, 500]);
      }

      // أنيميشن الظهور
      Animated.parallel([
        Animated.timing(fadeAnim, {
          toValue: 1,
          duration: 300,
          useNativeDriver: true,
        }),
        Animated.spring(slideAnim, {
          toValue: 0,
          tension: 50,
          friction: 8,
          useNativeDriver: true,
        }),
      ]).start();
    } else {
      StatusBar.setBarStyle('dark-content');
      
      // أنيميشن الاختفاء
      Animated.parallel([
        Animated.timing(fadeAnim, {
          toValue: 0,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.timing(slideAnim, {
          toValue: screenHeight,
          duration: 250,
          useNativeDriver: true,
        }),
      ]).start();
    }
  }, [visible, alerts]);

  const handleResolveAlert = (alertId: string) => {
    ReactNativeAlert.alert(
      'تأكيد المراجعة',
      'هل تأكدت من مراجعة هذا التنبيه والتعامل معه بشكل مناسب؟',
      [
        {
          text: 'إلغاء',
          style: 'cancel'
        },
        {
          text: 'تأكيد',
          style: 'default',
          onPress: () => onResolveAlert(alertId)
        }
      ]
    );
  };

  const handleEmergencyAction = (alert: SafetyAlert) => {
    ReactNativeAlert.alert(
      '🚨 إجراء طارئ',
      'هذا التنبيه يتطلب تدخلاً فورياً. ما الإجراء المطلوب؟',
      [
        {
          text: 'اتصال طوارئ',
          style: 'destructive',
          onPress: () => {
            if (onEmergencyAction) {
              onEmergencyAction(alert);
            }
          }
        },
        {
          text: 'مراجعة فورية',
          style: 'default',
          onPress: () => onViewDetails(alert)
        },
        {
          text: 'إلغاء',
          style: 'cancel'
        }
      ]
    );
  };

  const unresolvedAlerts = alerts.filter(alert => !alert.resolved);
  const resolvedAlerts = alerts.filter(alert => alert.resolved);
  const criticalCount = alerts.filter(alert => 
    alert.severity === 'critical' || alert.requires_immediate_action
  ).length;

  return (
    <Modal
      visible={visible}
      transparent={true}
      animationType="none"
      onRequestClose={onClose}
    >
      <Animated.View 
        style={[
          styles.modalOverlay,
          { opacity: fadeAnim }
        ]}
      >
        <Animated.View
          style={[
            styles.modalContainer,
            { transform: [{ translateY: slideAnim }] }
          ]}
        >
          {/* Header */}
          <View style={styles.modalHeader}>
            <View style={styles.headerLeft}>
              <Text style={styles.modalTitle}>
                🚨 تنبيهات الأمان
              </Text>
              <Text style={styles.alertsCount}>
                {unresolvedAlerts.length} غير محلول
                {criticalCount > 0 && (
                  <Text style={styles.criticalCount}>
                    {' '}• {criticalCount} حرج
                  </Text>
                )}
              </Text>
            </View>
            
            <TouchableOpacity
              style={styles.closeButton}
              onPress={onClose}
            >
              <Text style={styles.closeButtonText}>✖️</Text>
            </TouchableOpacity>
          </View>

          {/* Content */}
          <ScrollView 
            style={styles.alertsList}
            showsVerticalScrollIndicator={false}
          >
            {unresolvedAlerts.length === 0 && resolvedAlerts.length === 0 ? (
              <View style={styles.emptyState}>
                <Text style={styles.emptyStateText}>
                  ✅ لا توجد تنبيهات حالياً
                </Text>
                <Text style={styles.emptyStateSubtext}>
                  جميع التفاعلات آمنة ومناسبة
                </Text>
              </View>
            ) : (
              <>
                {/* التنبيهات غير المحلولة */}
                {unresolvedAlerts.length > 0 && (
                  <>
                    <Text style={styles.sectionTitle}>
                      ⚠️ تنبيهات تحتاج مراجعة ({unresolvedAlerts.length})
                    </Text>
                    {unresolvedAlerts.map((alert, index) => (
                      <AlertCard
                        key={alert.id}
                        alert={alert}
                        isFirst={index === 0}
                        onResolve={() => handleResolveAlert(alert.id)}
                        onViewDetails={() => onViewDetails(alert)}
                        onEmergencyAction={
                          alert.requires_immediate_action 
                            ? () => handleEmergencyAction(alert)
                            : undefined
                        }
                      />
                    ))}
                  </>
                )}

                {/* التنبيهات المحلولة */}
                {resolvedAlerts.length > 0 && (
                  <>
                    <Text style={styles.sectionTitle}>
                      ✅ تنبيهات محلولة ({resolvedAlerts.length})
                    </Text>
                    {resolvedAlerts.slice(0, 5).map((alert, index) => (
                      <AlertCard
                        key={alert.id}
                        alert={alert}
                        isFirst={false}
                        onResolve={() => {}}
                        onViewDetails={() => onViewDetails(alert)}
                      />
                    ))}
                    {resolvedAlerts.length > 5 && (
                      <Text style={styles.moreResolvedText}>
                        ... و {resolvedAlerts.length - 5} تنبيهات أخرى محلولة
                      </Text>
                    )}
                  </>
                )}
              </>
            )}
          </ScrollView>

          {/* Footer */}
          {unresolvedAlerts.length > 0 && (
            <View style={styles.modalFooter}>
              <Text style={styles.footerText}>
                💡 تأكد من مراجعة جميع التنبيهات لضمان سلامة طفلك
              </Text>
            </View>
          )}
        </Animated.View>
      </Animated.View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'flex-end',
  },
  modalContainer: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: screenHeight * 0.9,
    minHeight: screenHeight * 0.5,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
    backgroundColor: '#F8F9FA',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
  },
  headerLeft: {
    flex: 1,
  },
  modalTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#2C3E50',
    textAlign: 'right',
  },
  alertsCount: {
    fontSize: 14,
    color: '#7F8C8D',
    textAlign: 'right',
    marginTop: 4,
  },
  criticalCount: {
    color: '#E74C3C',
    fontWeight: 'bold',
  },
  closeButton: {
    padding: 10,
    marginLeft: 10,
  },
  closeButtonText: {
    fontSize: 18,
    color: '#7F8C8D',
  },
  alertsList: {
    flex: 1,
    padding: 15,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#2C3E50',
    textAlign: 'right',
    marginVertical: 15,
    paddingHorizontal: 5,
  },
  alertCard: {
    borderWidth: 2,
    borderRadius: 12,
    padding: 15,
    marginBottom: 15,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 3.84,
    elevation: 5,
  },
  alertHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  alertHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  typeIcon: {
    fontSize: 24,
    marginRight: 12,
  },
  alertTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    textAlign: 'right',
  },
  alertTime: {
    fontSize: 12,
    color: '#7F8C8D',
    textAlign: 'right',
    marginTop: 2,
  },
  alertHeaderRight: {
    alignItems: 'flex-end',
  },
  severityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  severityText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  alertContent: {
    marginBottom: 12,
  },
  alertDescription: {
    fontSize: 14,
    color: '#5D6D7E',
    textAlign: 'right',
    marginBottom: 8,
    lineHeight: 20,
  },
  alertMessage: {
    fontSize: 16,
    color: '#2C3E50',
    textAlign: 'right',
    fontStyle: 'italic',
    marginBottom: 10,
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: 'rgba(0, 0, 0, 0.05)',
    borderRadius: 8,
    lineHeight: 22,
  },
  contextInfo: {
    marginTop: 8,
  },
  contextText: {
    fontSize: 12,
    color: '#5D6D7E',
    textAlign: 'right',
    marginBottom: 4,
  },
  riskIndicator: {
    marginTop: 10,
  },
  riskText: {
    fontSize: 12,
    color: '#5D6D7E',
    textAlign: 'right',
    marginBottom: 5,
  },
  riskBar: {
    height: 4,
    backgroundColor: '#E0E0E0',
    borderRadius: 2,
    overflow: 'hidden',
  },
  riskBarFill: {
    height: '100%',
    borderRadius: 2,
  },
  alertActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    flexWrap: 'wrap',
    gap: 8,
  },
  actionButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    marginLeft: 5,
    marginBottom: 5,
  },
  emergencyButton: {
    backgroundColor: '#E74C3C',
  },
  emergencyButtonText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  detailsButton: {
    backgroundColor: '#3498DB',
  },
  detailsButtonText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  resolveButton: {
    backgroundColor: '#27AE60',
  },
  resolveButtonText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  resolvedBadge: {
    marginTop: 10,
    padding: 8,
    backgroundColor: 'rgba(39, 174, 96, 0.1)',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#27AE60',
  },
  resolvedText: {
    fontSize: 12,
    color: '#27AE60',
    textAlign: 'right',
    fontWeight: 'bold',
  },
  resolvedByText: {
    fontSize: 10,
    color: '#5D6D7E',
    textAlign: 'right',
    marginTop: 2,
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyStateText: {
    fontSize: 18,
    color: '#27AE60',
    textAlign: 'center',
    fontWeight: 'bold',
  },
  emptyStateSubtext: {
    fontSize: 14,
    color: '#7F8C8D',
    textAlign: 'center',
    marginTop: 8,
  },
  moreResolvedText: {
    fontSize: 14,
    color: '#7F8C8D',
    textAlign: 'center',
    fontStyle: 'italic',
    marginVertical: 15,
  },
  modalFooter: {
    padding: 15,
    backgroundColor: '#F8F9FA',
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
  },
  footerText: {
    fontSize: 12,
    color: '#5D6D7E',
    textAlign: 'center',
    lineHeight: 16,
  },
});

export default AlertModal;
