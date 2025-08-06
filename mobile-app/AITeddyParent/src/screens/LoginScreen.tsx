import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ApiService } from '../services/api';
import { LoginCredentials } from '../types';
import { SecureStorage } from '../services/SecureStorageService';
import { DEV_CREDENTIALS } from '../config/dev-credentials';

interface LoginScreenProps {
  onLoginSuccess: () => void;
}

export default function LoginScreen({ onLoginSuccess }: LoginScreenProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  // دالة للتعبئة السريعة ببيانات الاختبار
  const fillTestCredentials = (type: 'simple' | 'standard' = 'simple') => {
    if (type === 'simple') {
      setEmail(DEV_CREDENTIALS.simpleEmail);
      setPassword(DEV_CREDENTIALS.simplePassword);
    } else {
      setEmail(DEV_CREDENTIALS.email);
      setPassword(DEV_CREDENTIALS.password);
    }
  };

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('خطأ', 'يرجى ملء جميع الحقول');
      return;
    }

    setLoading(true);
    try {
      const credentials: LoginCredentials = { email, password };
      const response = await ApiService.login(credentials);
      
      // Store auth token securely
      await SecureStorage.setToken(response.access_token);
      // Store non-sensitive user data in AsyncStorage
      await AsyncStorage.setItem('user', JSON.stringify(response.user));
      
      Alert.alert('نجح!', 'تم تسجيل الدخول بنجاح');
      onLoginSuccess();
    } catch (error: any) {
      console.error('Login error:', error);
      const message = error.response?.data?.detail || 'فشل في تسجيل الدخول';
      Alert.alert('خطأ', message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={styles.content}>
        <Text style={styles.title}>🧸 AI Teddy Bear</Text>
        <Text style={styles.subtitle}>تطبيق مراقبة الوالدين</Text>

        <View style={styles.form}>
          <TextInput
            style={styles.input}
            placeholder="البريد الإلكتروني"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            placeholderTextColor="#666"
          />

          <TextInput
            style={styles.input}
            placeholder="كلمة المرور"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholderTextColor="#666"
          />

          <TouchableOpacity
            style={[styles.button, loading && styles.buttonDisabled]}
            onPress={handleLogin}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>تسجيل الدخول</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* أزرار التعبئة السريعة للاختبار */}
        <View style={styles.testButtons}>
          <TouchableOpacity
            style={styles.testButton}
            onPress={() => fillTestCredentials('simple')}
          >
            <Text style={styles.testButtonText}>تعبئة سريعة: a@a.com / 123</Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[styles.testButton, styles.testButtonSecondary]}
            onPress={() => fillTestCredentials('standard')}
          >
            <Text style={styles.testButtonTextSecondary}>تعبئة: test@test.com / 123456</Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.demo}>
          للاختبار السريع:
          {'\n'}البريد: a@a.com
          {'\n'}كلمة المرور: 123
        </Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 30,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 10,
    color: '#333',
  },
  subtitle: {
    fontSize: 18,
    textAlign: 'center',
    marginBottom: 40,
    color: '#666',
  },
  form: {
    marginBottom: 30,
  },
  input: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 15,
    fontSize: 16,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: '#ddd',
    textAlign: 'right',
  },
  button: {
    backgroundColor: '#007AFF',
    borderRadius: 10,
    padding: 15,
    alignItems: 'center',
    marginTop: 10,
  },
  buttonDisabled: {
    backgroundColor: '#ccc',
  },
  buttonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  demo: {
    textAlign: 'center',
    color: '#888',
    fontSize: 14,
    lineHeight: 20,
  },
  testButtons: {
    marginBottom: 20,
    gap: 10,
  },
  testButton: {
    backgroundColor: '#28a745',
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
  },
  testButtonSecondary: {
    backgroundColor: '#17a2b8',
  },
  testButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  testButtonTextSecondary: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
});
