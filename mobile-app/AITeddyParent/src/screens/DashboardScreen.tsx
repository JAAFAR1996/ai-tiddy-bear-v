import React, { useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  Alert,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { ApiService } from '../services/api';
import { Child, Interaction, SafetyAlert } from '../types';
import { useAuthStore, useFamilyStore, useAppState, useAppActions } from '../store/AppStore';

interface DashboardScreenProps {
  onLogout: () => void;
}

export default function DashboardScreen({ onLogout }: DashboardScreenProps) {
  // Global state
  const { user } = useAuthStore();
  const {
    children,
    selectedChildId,
    interactions,
    safetyAlerts,
    childrenLoading,
    interactionsLoading,
    alertsLoading,
    setChildren,
    selectChild,
    setInteractions,
    setSafetyAlerts,
    setChildrenLoading,
    setInteractionsLoading,
    setAlertsLoading,
  } = useFamilyStore();

  const { isLoading, hasUnresolvedAlerts, selectedChild } = useAppState();
  const { logout } = useAppActions();

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setChildrenLoading(true);
      const childrenData = await ApiService.getChildren();
      // Convert ApiChild to Child format
      const convertedChildren: Child[] = childrenData.map(child => ({
        ...child,
        last_interaction: child.created_at, // Use created_at as fallback
        preferences: {} // Empty preferences as default
      }));
      setChildren(convertedChildren);
      
      // Load safety alerts
      setAlertsLoading(true);
      const alertsData = await ApiService.getSafetyAlerts();
      const convertedAlerts: SafetyAlert[] = alertsData.map(alert => ({
        ...alert,
        child_name: alert.child_name || 'Unknown Child',
        type: (alert.type || 'inappropriate_interaction') as 'forbidden_content' | 'self_harm' | 'excessive_usage' | 'inappropriate_interaction' | 'emergency',
        severity: (alert.severity || 'medium') as 'low' | 'medium' | 'high' | 'critical',
        resolved: alert.resolved || false,
        risk_score: alert.risk_score || 0,
        auto_resolved: alert.auto_resolved || false,
        requires_immediate_action: alert.requires_immediate_action || false,
        escalation_level: alert.escalation_level || 0,
        details: alert.details || alert.message
      }));
      setSafetyAlerts(convertedAlerts);
      setAlertsLoading(false);
      
      if (childrenData.length > 0) {
        // Load interactions for first child by default
        loadChildInteractions(childrenData[0].id);
      }
    } catch (error: any) {
      console.error('Error loading dashboard:', error);
      Alert.alert('خطأ', 'فشل في تحميل البيانات');
    } finally {
      setChildrenLoading(false);
    }
  };

  const loadChildInteractions = async (childId: string) => {
    try {
      selectChild(childId);
      setInteractionsLoading(true);
      const interactionsData = await ApiService.getChildInteractions(childId, 10);
      setInteractions(interactionsData as Interaction[]);
    } catch (error) {
      console.error('Error loading interactions:', error);
      Alert.alert('خطأ', 'فشل في تحميل التفاعلات');
    } finally {
      setInteractionsLoading(false);
    }
  };

  const onRefresh = async () => {
    await loadDashboardData();
  };

  const handleLogout = async () => {
    Alert.alert(
      'تسجيل الخروج',
      'هل أنت متأكد من تسجيل الخروج؟',
      [
        { text: 'إلغاء', style: 'cancel' },
        {
          text: 'خروج',
          style: 'destructive',
          onPress: async () => {
            await ApiService.logout();
            logout(); // Clear all state
            onLogout();
          },
        },
      ]
    );
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('ar');
  };

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'forbidden_content':
        return '⚠️';
      case 'usage_limit':
        return '⏰';
      default:
        return '🔔';
    }
  };

  const renderChildCard = ({ item }: { item: Child }) => {
    const hasAlerts = safetyAlerts.some(alert => alert.child_id === item.id && !alert.resolved);
    
    return (
      <TouchableOpacity
        style={[styles.childCard, selectedChildId === item.id && styles.selectedCard]}
        onPress={() => loadChildInteractions(item.id)}
      >
        <View style={styles.childHeader}>
          <Text style={styles.childName}>{item.name}</Text>
          <Text style={styles.childAge}>{item.age} سنوات</Text>
          {hasAlerts && <Text style={styles.alertBadge}>⚠️</Text>}
        </View>
        <Text style={styles.lastInteraction}>
          آخر تفاعل: {formatTime(item.last_interaction)}
        </Text>
      </TouchableOpacity>
    );
  };

  const renderInteraction = ({ item }: { item: Interaction }) => (
    <View style={[
      styles.interactionCard,
      item.has_forbidden_content && styles.warningCard
    ]}>
      <View style={styles.interactionHeader}>
        <Text style={styles.interactionTime}>{formatTime(item.timestamp)}</Text>
        {item.has_forbidden_content && <Text style={styles.warningIcon}>⚠️</Text>}
      </View>
      <Text style={styles.question}>س: {item.question}</Text>
      <Text style={styles.response}>ج: {item.response}</Text>
      <Text style={styles.duration}>مدة الاستخدام: {item.usage_duration} ثانية</Text>
    </View>
  );

  const renderAlert = ({ item }: { item: SafetyAlert }) => (
    <View style={styles.alertCard}>
      <View style={styles.alertHeader}>
        <Text style={styles.alertIcon}>{getAlertIcon(item.alert_type || item.type)}</Text>
        <Text style={styles.alertTime}>{formatTime(item.timestamp)}</Text>
      </View>
      <Text style={styles.alertMessage}>{item.message}</Text>
    </View>
  );

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>جاري تحميل البيانات...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>مرحباً {user?.name}</Text>
        <TouchableOpacity onPress={handleLogout} style={styles.logoutButton}>
          <Text style={styles.logoutText}>خروج</Text>
        </TouchableOpacity>
      </View>

      {/* Safety Alerts */}
      {hasUnresolvedAlerts && (
        <View style={styles.alertsSection}>
          <Text style={styles.sectionTitle}>🚨 تنبيهات الأمان</Text>
          <FlatList
            data={safetyAlerts.filter(alert => !alert.resolved)}
            renderItem={renderAlert}
            keyExtractor={(item) => item.id}
            horizontal
            showsHorizontalScrollIndicator={false}
          />
        </View>
      )}

      {/* Children List */}
      <View style={styles.childrenSection}>
        <Text style={styles.sectionTitle}>👶 الأطفال ({children.length})</Text>
        <FlatList
          data={children}
          renderItem={renderChildCard}
          keyExtractor={(item) => item.id}
          horizontal
          showsHorizontalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={childrenLoading} onRefresh={onRefresh} />
          }
        />
      </View>

      {/* Interactions */}
      <View style={styles.interactionsSection}>
        <Text style={styles.sectionTitle}>
          💬 آخر التفاعلات {selectedChild && `- ${selectedChild.name}`}
        </Text>
        <FlatList
          data={interactions}
          renderItem={renderInteraction}
          keyExtractor={(item) => item.id}
          style={styles.interactionsList}
          showsVerticalScrollIndicator={false}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#666',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
  },
  logoutButton: {
    padding: 10,
  },
  logoutText: {
    color: '#FF3B30',
    fontSize: 16,
  },
  alertsSection: {
    padding: 20,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 15,
    color: '#333',
  },
  alertCard: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    marginRight: 10,
    borderLeftWidth: 4,
    borderLeftColor: '#FF3B30',
    minWidth: 200,
  },
  alertHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 5,
  },
  alertIcon: {
    fontSize: 20,
  },
  alertTime: {
    fontSize: 12,
    color: '#666',
  },
  alertMessage: {
    fontSize: 14,
    color: '#333',
  },
  childrenSection: {
    padding: 20,
  },
  childCard: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    marginRight: 15,
    minWidth: 150,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  selectedCard: {
    borderColor: '#007AFF',
  },
  childHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  childName: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  childAge: {
    fontSize: 14,
    color: '#666',
  },
  alertBadge: {
    fontSize: 20,
  },
  lastInteraction: {
    fontSize: 12,
    color: '#888',
  },
  interactionsSection: {
    flex: 1,
    padding: 20,
  },
  interactionsList: {
    flex: 1,
  },
  interactionCard: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    marginBottom: 10,
  },
  warningCard: {
    backgroundColor: '#FFF3CD',
    borderLeftWidth: 4,
    borderLeftColor: '#FF3B30',
  },
  interactionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  interactionTime: {
    fontSize: 12,
    color: '#666',
  },
  warningIcon: {
    fontSize: 16,
  },
  question: {
    fontSize: 14,
    color: '#333',
    marginBottom: 5,
    textAlign: 'right',
  },
  response: {
    fontSize: 14,
    color: '#555',
    marginBottom: 10,
    textAlign: 'right',
  },
  duration: {
    fontSize: 12,
    color: '#888',
    textAlign: 'right',
  },
});
