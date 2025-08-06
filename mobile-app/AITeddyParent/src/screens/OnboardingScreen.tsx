/**
 * Onboarding Screen - شاشة التعريف
 * 
 * Features:
 * - Welcome message
 * - Privacy Policy and Terms acceptance
 * - Essential permissions setup
 * - Safety guidelines
 * - Parent verification
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Alert,
  Modal,
} from 'react-native';
import PrivacyPolicyScreen from './PrivacyPolicyScreen';
import TermsOfServiceScreen from './TermsOfServiceScreen';

interface OnboardingScreenProps {
  onComplete: () => void;
}

export default function OnboardingScreen({ onComplete }: OnboardingScreenProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [showPrivacyPolicy, setShowPrivacyPolicy] = useState(false);
  const [showTermsOfService, setShowTermsOfService] = useState(false);
  const [acceptedPrivacy, setAcceptedPrivacy] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);

  const steps = [
    {
      title: 'مرحباً بك في AI Teddy Parent 🧸',
      content: 'تطبيق مراقبة والدية آمن لحماية أطفالك أثناء التفاعل مع الدب الذكي',
      icon: '🛡️',
    },
    {
      title: 'أمان الأطفال أولويتنا القصوى 🚨',
      content: 'نراقب جميع التفاعلات ونرسل تنبيهات فورية لأي محتوى غير مناسب',
      icon: '👥',
    },
    {
      title: 'الخصوصية والشروط القانونية ⚖️',
      content: 'يرجى مراجعة وقبول سياسة الخصوصية وشروط الاستخدام للمتابعة',
      icon: '📋',
    },
  ];

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      // At the legal step
      if (!acceptedPrivacy || !acceptedTerms) {
        Alert.alert(
          'موافقة مطلوبة',
          'يرجى مراجعة وقبول سياسة الخصوصية وشروط الاستخدام للمتابعة',
          [{ text: 'حسناً', style: 'default' }]
        );
        return;
      }
      
      // All requirements met
      Alert.alert(
        'مرحباً بك!',
        'تم قبول الشروط بنجاح. يمكنك الآن استخدام التطبيق بأمان.',
        [
          {
            text: 'ابدأ الاستخدام',
            onPress: onComplete,
          },
        ]
      );
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handlePrivacyAccept = () => {
    setAcceptedPrivacy(true);
    setShowPrivacyPolicy(false);
    Alert.alert('تم!', 'تم قبول سياسة الخصوصية');
  };

  const handlePrivacyDecline = () => {
    setShowPrivacyPolicy(false);
    Alert.alert(
      'مطلوب للمتابعة',
      'سياسة الخصوصية مطلوبة لاستخدام التطبيق وحماية بيانات طفلك'
    );
  };

  const handleTermsAccept = () => {
    setAcceptedTerms(true);
    setShowTermsOfService(false);
    Alert.alert('تم!', 'تم قبول شروط الاستخدام');
  };

  const handleTermsDecline = () => {
    setShowTermsOfService(false);
    Alert.alert(
      'مطلوب للمتابعة',
      'شروط الاستخدام مطلوبة لضمان الاستخدام الآمن للتطبيق'
    );
  };

  const renderStepContent = () => {
    const step = steps[currentStep];

    if (currentStep === 2) {
      // Legal agreements step
      return (
        <View style={styles.legalStep}>
          <Text style={styles.legalTitle}>المتطلبات القانونية</Text>
          <Text style={styles.legalDescription}>
            لضمان أمان طفلك وحماية بياناته، يرجى مراجعة وقبول الوثائق التالية:
          </Text>

          <View style={styles.documentSection}>
            <TouchableOpacity
              style={[
                styles.documentButton,
                acceptedPrivacy && styles.documentButtonAccepted
              ]}
              onPress={() => setShowPrivacyPolicy(true)}
            >
              <Text style={styles.documentIcon}>🔒</Text>
              <View style={styles.documentInfo}>
                <Text style={styles.documentTitle}>سياسة الخصوصية</Text>
                <Text style={styles.documentDescription}>
                  كيف نحمي بيانات طفلك وخصوصيته
                </Text>
              </View>
              <Text style={styles.documentStatus}>
                {acceptedPrivacy ? '✅' : '📋'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.documentButton,
                acceptedTerms && styles.documentButtonAccepted
              ]}
              onPress={() => setShowTermsOfService(true)}
            >
              <Text style={styles.documentIcon}>⚖️</Text>
              <View style={styles.documentInfo}>
                <Text style={styles.documentTitle}>شروط الاستخدام</Text>
                <Text style={styles.documentDescription}>
                  قواعد وضوابط الاستخدام الآمن
                </Text>
              </View>
              <Text style={styles.documentStatus}>
                {acceptedTerms ? '✅' : '📋'}
              </Text>
            </TouchableOpacity>
          </View>

          <View style={styles.requirementsList}>
            <Text style={styles.requirementsTitle}>متطلبات الاستخدام:</Text>
            <Text style={styles.requirementItem}>✓ أن تكون والد أو وصي قانوني</Text>
            <Text style={styles.requirementItem}>✓ العمر 18 سنة فأكثر</Text>
            <Text style={styles.requirementItem}>✓ الإشراف المباشر على الطفل</Text>
            <Text style={styles.requirementItem}>✓ الاستجابة لتنبيهات الأمان</Text>
          </View>
        </View>
      );
    }

    return (
      <View style={styles.stepContent}>
        <Text style={styles.stepIcon}>{step.icon}</Text>
        <Text style={styles.stepTitle}>{step.title}</Text>
        <Text style={styles.stepDescription}>{step.content}</Text>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.appTitle}>🧸 AI Teddy Parent</Text>
        <View style={styles.progressContainer}>
          {steps.map((_, index) => (
            <View
              key={index}
              style={[
                styles.progressDot,
                index <= currentStep && styles.progressDotActive,
              ]}
            />
          ))}
        </View>
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.contentContainer}>
        {renderStepContent()}
      </ScrollView>

      <View style={styles.footer}>
        <View style={styles.buttonContainer}>
          {currentStep > 0 && (
            <TouchableOpacity style={styles.backButton} onPress={handleBack}>
              <Text style={styles.backButtonText}>← السابق</Text>
            </TouchableOpacity>
          )}
          
          <TouchableOpacity
            style={[
              styles.nextButton,
              currentStep === 2 && (!acceptedPrivacy || !acceptedTerms) && styles.nextButtonDisabled
            ]}
            onPress={handleNext}
            disabled={currentStep === 2 && (!acceptedPrivacy || !acceptedTerms)}
          >
            <Text style={styles.nextButtonText}>
              {currentStep === steps.length - 1 ? 'ابدأ الاستخدام' : 'التالي →'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Privacy Policy Modal */}
      <Modal
        visible={showPrivacyPolicy}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        <View style={styles.modalContainer}>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={() => setShowPrivacyPolicy(false)}
          >
            <Text style={styles.closeButtonText}>× إغلاق</Text>
          </TouchableOpacity>
          <PrivacyPolicyScreen
            showActions={true}
            onAccept={handlePrivacyAccept}
            onDecline={handlePrivacyDecline}
          />
        </View>
      </Modal>

      {/* Terms of Service Modal */}
      <Modal
        visible={showTermsOfService}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        <View style={styles.modalContainer}>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={() => setShowTermsOfService(false)}
          >
            <Text style={styles.closeButtonText}>× إغلاق</Text>
          </TouchableOpacity>
          <TermsOfServiceScreen
            showActions={true}
            onAccept={handleTermsAccept}
            onDecline={handleTermsDecline}
          />
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: '#007AFF',
    padding: 20,
    paddingTop: 50,
    alignItems: 'center',
  },
  appTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 20,
  },
  progressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  progressDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.3)',
    marginHorizontal: 6,
  },
  progressDotActive: {
    backgroundColor: '#fff',
  },
  content: {
    flex: 1,
  },
  contentContainer: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 30,
  },
  stepContent: {
    alignItems: 'center',
    textAlign: 'center',
  },
  stepIcon: {
    fontSize: 80,
    marginBottom: 30,
  },
  stepTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    textAlign: 'center',
    marginBottom: 20,
  },
  stepDescription: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    lineHeight: 24,
  },
  legalStep: {
    flex: 1,
  },
  legalTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    textAlign: 'center',
    marginBottom: 15,
  },
  legalDescription: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 30,
  },
  documentSection: {
    marginBottom: 30,
  },
  documentButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 10,
    marginBottom: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  documentButtonAccepted: {
    backgroundColor: '#E8F5E8',
    borderColor: '#34C759',
    borderWidth: 2,
  },
  documentIcon: {
    fontSize: 24,
    marginRight: 15,
  },
  documentInfo: {
    flex: 1,
  },
  documentTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
    textAlign: 'right',
  },
  documentDescription: {
    fontSize: 14,
    color: '#666',
    textAlign: 'right',
    marginTop: 2,
  },
  documentStatus: {
    fontSize: 24,
    marginLeft: 10,
  },
  requirementsList: {
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  requirementsTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
    textAlign: 'right',
    marginBottom: 10,
  },
  requirementItem: {
    fontSize: 14,
    color: '#444',
    textAlign: 'right',
    marginBottom: 5,
    paddingRight: 10,
  },
  footer: {
    padding: 20,
    backgroundColor: '#fff',
    borderTopWidth: 1,
    borderTopColor: '#eee',
  },
  buttonContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  backButton: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: '#f0f0f0',
    borderRadius: 8,
  },
  backButtonText: {
    fontSize: 16,
    color: '#666',
  },
  nextButton: {
    paddingHorizontal: 30,
    paddingVertical: 15,
    backgroundColor: '#007AFF',
    borderRadius: 8,
    flex: 0.6,
    alignItems: 'center',
  },
  nextButtonDisabled: {
    backgroundColor: '#ccc',
  },
  nextButtonText: {
    fontSize: 16,
    color: '#fff',
    fontWeight: 'bold',
  },
  modalContainer: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  closeButton: {
    position: 'absolute',
    top: 50,
    right: 20,
    zIndex: 1000,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    paddingHorizontal: 15,
    paddingVertical: 8,
    borderRadius: 20,
  },
  closeButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
});