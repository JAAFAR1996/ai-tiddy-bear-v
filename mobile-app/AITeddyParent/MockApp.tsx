import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert } from 'react-native';

// Mock data for testing
const mockChildren = [
  { id: '1', name: 'أحمد', age: 8, last_interaction: '2025-08-04T10:30:00' },
  { id: '2', name: 'فاطمة', age: 6, last_interaction: '2025-08-04T09:15:00' },
];

const mockInteractions = [
  {
    id: '1',
    child_id: '1',
    question: 'ما هو لونك المفضل؟',
    response: 'لوني المفضل هو الأزرق!',
    timestamp: '2025-08-04T10:30:00',
    has_forbidden_content: false,
    usage_duration: 45,
  },
  {
    id: '2',
    child_id: '1',
    question: 'احكي لي قصة',
    response: 'يحكى أن هناك أرنب صغير...',
    timestamp: '2025-08-04T10:25:00',
    has_forbidden_content: false,
    usage_duration: 120,
  },
  {
    id: '3',
    child_id: '1',
    question: 'كلمة سيئة',
    response: 'آسف، لا يمكنني قول ذلك',
    timestamp: '2025-08-04T10:20:00',
    has_forbidden_content: true,
    usage_duration: 15,
  },
];

export default function MockApp() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [selectedChild, setSelectedChild] = useState(mockChildren[0]);

  const handleLogin = () => {
    Alert.alert('تم!', 'تم تسجيل الدخول بنجاح', [
      { text: 'موافق', onPress: () => setIsLoggedIn(true) }
    ]);
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return `${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`;
  };

  if (!isLoggedIn) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>🧸 AI Teddy Parent</Text>
        <Text style={styles.subtitle}>تطبيق مراقبة الوالدين</Text>
        
        <TouchableOpacity style={styles.button} onPress={handleLogin}>
          <Text style={styles.buttonText}>تسجيل الدخول (تجريبي)</Text>
        </TouchableOpacity>
        
        <Text style={styles.note}>
          هذا مثال تجريبي للتطبيق{'\n'}
          البيانات وهمية للاختبار
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>مرحباً والد/والدة</Text>
        <TouchableOpacity onPress={() => setIsLoggedIn(false)}>
          <Text style={styles.logoutText}>خروج</Text>
        </TouchableOpacity>
      </View>

      {/* Children Cards */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>👶 الأطفال ({mockChildren.length})</Text>
        <View style={styles.childrenContainer}>
          {mockChildren.map((child) => (
            <TouchableOpacity
              key={child.id}
              style={[
                styles.childCard,
                selectedChild.id === child.id && styles.selectedCard
              ]}
              onPress={() => setSelectedChild(child)}
            >
              <Text style={styles.childName}>{child.name}</Text>
              <Text style={styles.childAge}>{child.age} سنوات</Text>
              <Text style={styles.lastInteraction}>
                آخر تفاعل: {formatTime(child.last_interaction)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Interactions */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>
          💬 آخر التفاعلات - {selectedChild.name}
        </Text>
        
        {mockInteractions
          .filter(interaction => interaction.child_id === selectedChild.id)
          .map((interaction) => (
            <View
              key={interaction.id}
              style={[
                styles.interactionCard,
                interaction.has_forbidden_content && styles.warningCard
              ]}
            >
              <View style={styles.interactionHeader}>
                <Text style={styles.interactionTime}>
                  {formatTime(interaction.timestamp)}
                </Text>
                {interaction.has_forbidden_content && (
                  <Text style={styles.warningIcon}>⚠️</Text>
                )}
              </View>
              
              <Text style={styles.question}>س: {interaction.question}</Text>
              <Text style={styles.response}>ج: {interaction.response}</Text>
              <Text style={styles.duration}>
                المدة: {interaction.usage_duration} ثانية
              </Text>
              
              {interaction.has_forbidden_content && (
                <Text style={styles.warningText}>
                  🚨 تم كشف محتوى غير مناسب
                </Text>
              )}
            </View>
          ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 20,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 10,
    color: '#333',
    marginTop: 60,
  },
  subtitle: {
    fontSize: 18,
    textAlign: 'center',
    marginBottom: 40,
    color: '#666',
  },
  button: {
    backgroundColor: '#007AFF',
    borderRadius: 10,
    padding: 15,
    alignItems: 'center',
    marginBottom: 20,
  },
  buttonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  note: {
    textAlign: 'center',
    color: '#888',
    fontSize: 14,
    lineHeight: 20,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
    marginTop: 40,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
  },
  logoutText: {
    color: '#FF3B30',
    fontSize: 16,
  },
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 15,
    color: '#333',
  },
  childrenContainer: {
    flexDirection: 'row',
    gap: 10,
  },
  childCard: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    flex: 1,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  selectedCard: {
    borderColor: '#007AFF',
  },
  childName: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
    textAlign: 'center',
  },
  childAge: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    marginVertical: 5,
  },
  lastInteraction: {
    fontSize: 12,
    color: '#888',
    textAlign: 'center',
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
  warningText: {
    fontSize: 12,
    color: '#FF3B30',
    fontWeight: 'bold',
    textAlign: 'center',
    marginTop: 5,
  },
});
