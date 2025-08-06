/**
 * Privacy Policy Screen - سياسة الخصوصية
 * 
 * Features:
 * - COPPA-compliant privacy policy
 * - Arabic language support
 * - Child data protection information
 * - Easy-to-understand language
 * - Scrollable content
 * - Legal compliance for app stores
 */

import React from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { config } from '../config';

interface PrivacyPolicyScreenProps {
  onAccept?: () => void;
  onDecline?: () => void;
  showActions?: boolean;
}

export default function PrivacyPolicyScreen({
  onAccept,
  onDecline,
  showActions = false,
}: PrivacyPolicyScreenProps) {
  const handleAccept = () => {
    Alert.alert(
      'قبول سياسة الخصوصية',
      'هل توافق على سياسة الخصوصية وشروط الاستخدام؟',
      [
        { text: 'لا', style: 'cancel', onPress: onDecline },
        { text: 'نعم، أوافق', onPress: onAccept },
      ]
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>سياسة الخصوصية</Text>
        <Text style={styles.headerSubtitle}>
          تطبيق AI Teddy Bear - مراقبة الوالدين
        </Text>
        <Text style={styles.lastUpdated}>
          آخر تحديث: {new Date().toLocaleDateString('ar')}
        </Text>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={true}>
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🛡️ التزامنا بحماية خصوصية الأطفال</Text>
          <Text style={styles.sectionText}>
            نحن ملتزمون بحماية خصوصية الأطفال وفقاً لقانون حماية خصوصية الأطفال على الإنترنت (COPPA). 
            هذا التطبيق مخصص للوالدين لمراقبة تفاعلات أطفالهم مع الدب الذكي AI Teddy Bear بطريقة آمنة ومحمية.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📱 حول هذا التطبيق</Text>
          <Text style={styles.sectionText}>
            تطبيق AI Teddy Parent هو تطبيق مراقبة والدية يسمح للوالدين بمراقبة التفاعلات بين أطفالهم والدب الذكي. 
            التطبيق يوفر تنبيهات الأمان، تقارير الاستخدام، وأدوات الرقابة الوالدية.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>👥 من يمكنه استخدام التطبيق</Text>
          <Text style={styles.bulletPoint}>• الوالدين والأوصياء القانونيين (18 سنة فأكثر)</Text>
          <Text style={styles.bulletPoint}>• المعلمين المخولين في البيئات التعليمية</Text>
          <Text style={styles.bulletPoint}>• مقدمي الرعاية المعتمدين</Text>
          <Text style={styles.sectionText}>
            هذا التطبيق غير مخصص للاستخدام المباشر من قبل الأطفال دون إشراف الوالدين.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📊 البيانات التي نجمعها</Text>
          
          <Text style={styles.subsectionTitle}>بيانات الوالدين:</Text>
          <Text style={styles.bulletPoint}>• الاسم والبريد الإلكتروني</Text>
          <Text style={styles.bulletPoint}>• كلمة المرور المشفرة</Text>
          <Text style={styles.bulletPoint}>• إعدادات الحساب والتفضيلات</Text>
          
          <Text style={styles.subsectionTitle}>بيانات الأطفال (بإذن الوالدين فقط):</Text>
          <Text style={styles.bulletPoint}>• الاسم الأول والعمر</Text>
          <Text style={styles.bulletPoint}>• تسجيلات التفاعلات الصوتية مع الدب</Text>
          <Text style={styles.bulletPoint}>• إحصائيات الاستخدام والوقت المستغرق</Text>
          <Text style={styles.bulletPoint}>• تنبيهات الأمان والمحتوى المفلتر</Text>
          
          <Text style={styles.subsectionTitle}>البيانات التقنية:</Text>
          <Text style={styles.bulletPoint}>• معرف الجهاز ونوع النظام</Text>
          <Text style={styles.bulletPoint}>• عنوان IP ومعلومات الشبكة</Text>
          <Text style={styles.bulletPoint}>• سجلات استخدام التطبيق</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🔒 كيف نحمي البيانات</Text>
          <Text style={styles.bulletPoint}>• تشفير جميع البيانات الحساسة</Text>
          <Text style={styles.bulletPoint}>• تخزين آمن في خوادم معتمدة</Text>
          <Text style={styles.bulletPoint}>• اتصالات مشفرة (HTTPS/WSS)</Text>
          <Text style={styles.bulletPoint}>• مراجعة أمنية دورية</Text>
          <Text style={styles.bulletPoint}>• وصول محدود للموظفين المخولين فقط</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🎯 كيف نستخدم البيانات</Text>
          <Text style={styles.bulletPoint}>• توفير خدمات المراقبة الوالدية</Text>
          <Text style={styles.bulletPoint}>• إرسال تنبيهات الأمان الفورية</Text>
          <Text style={styles.bulletPoint}>• إنتاج تقارير الاستخدام والتقدم</Text>
          <Text style={styles.bulletPoint}>• تحسين خوارزميات الأمان</Text>
          <Text style={styles.bulletPoint}>• الدعم التقني وحل المشاكل</Text>
          
          <Text style={styles.warningText}>
            ⚠️ نحن لا نبيع أو نؤجر أو نشارك بيانات الأطفال مع أطراف ثالثة للأغراض التجارية.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>👪 حقوق الوالدين</Text>
          <Text style={styles.bulletPoint}>• مراجعة جميع بيانات الطفل</Text>
          <Text style={styles.bulletPoint}>• حذف بيانات الطفل في أي وقت</Text>
          <Text style={styles.bulletPoint}>• منع جمع المزيد من البيانات</Text>
          <Text style={styles.bulletPoint}>• تحديث أو تصحيح البيانات</Text>
          <Text style={styles.bulletPoint}>• سحب الموافقة في أي وقت</Text>
          
          <Text style={styles.sectionText}>
            للاستفادة من هذه الحقوق، يرجى التواصل معنا عبر: privacy@aiteddybear.com
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🗂️ الاحتفاظ بالبيانات</Text>
          <Text style={styles.bulletPoint}>• بيانات التفاعلات: 90 يوماً كحد أقصى</Text>
          <Text style={styles.bulletPoint}>• تنبيهات الأمان: 12 شهراً للسجلات</Text>
          <Text style={styles.bulletPoint}>• بيانات الحساب: حتى إغلاق الحساب</Text>
          <Text style={styles.bulletPoint}>• السجلات التقنية: 30 يوماً</Text>
          
          <Text style={styles.sectionText}>
            يتم حذف جميع البيانات تلقائياً بعد انتهاء فترة الاحتفاظ أو عند طلب الوالدين.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🌍 نقل البيانات</Text>
          <Text style={styles.sectionText}>
            يتم تخزين البيانات في خوادم آمنة في المملكة العربية السعودية. 
            في حالات نادرة، قد نحتاج لنقل البيانات لخوادم في دول أخرى ملتزمة بمعايير الحماية الدولية.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📧 التواصل والشكاوى</Text>
          <Text style={styles.sectionText}>
            لأي استفسارات حول الخصوصية أو للإبلاغ عن مشاكل:
          </Text>
          <Text style={styles.contactInfo}>📧 البريد الإلكتروني: privacy@aiteddybear.com</Text>
          <Text style={styles.contactInfo}>📞 الهاتف: +966-50-123-4567</Text>
          <Text style={styles.contactInfo}>📍 العنوان: الرياض، المملكة العربية السعودية</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>⚖️ الامتثال القانوني</Text>
          <Text style={styles.sectionText}>
            هذا التطبيق ملتزم بالقوانين التالية:
          </Text>
          <Text style={styles.bulletPoint}>• قانون حماية البيانات السعودي</Text>
          <Text style={styles.bulletPoint}>• قانون COPPA الأمريكي</Text>
          <Text style={styles.bulletPoint}>• لائحة GDPR الأوروبية</Text>
          <Text style={styles.bulletPoint}>• معايير أمان ISO 27001</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🔄 تحديثات السياسة</Text>
          <Text style={styles.sectionText}>
            قد نقوم بتحديث سياسة الخصوصية من وقت لآخر. سيتم إشعارك بأي تغييرات مهمة عبر:
          </Text>
          <Text style={styles.bulletPoint}>• إشعار في التطبيق</Text>
          <Text style={styles.bulletPoint}>• رسالة بريد إلكتروني</Text>
          <Text style={styles.bulletPoint}>• تحديث تاريخ "آخر تحديث" أعلاه</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🔐 أمان الأطفال أولويتنا</Text>
          <Text style={styles.warningText}>
            نحن ملتزمون بجعل تفاعل الأطفال مع الذكاء الاصطناعي آمناً وتعليمياً ومفيداً. 
            جميع التفاعلات مراقبة ومفلترة لضمان المحتوى المناسب للعمر.
          </Text>
        </View>

        {showActions && (
          <View style={styles.actionsSection}>
            <TouchableOpacity style={styles.acceptButton} onPress={handleAccept}>
              <Text style={styles.acceptButtonText}>✅ أوافق على سياسة الخصوصية</Text>
            </TouchableOpacity>
            
            <TouchableOpacity style={styles.declineButton} onPress={onDecline}>
              <Text style={styles.declineButtonText}>❌ لا أوافق</Text>
            </TouchableOpacity>
          </View>
        )}

        <View style={styles.footer}>
          <Text style={styles.footerText}>
            © 2025 AI Teddy Bear. جميع الحقوق محفوظة.
          </Text>
          <Text style={styles.footerText}>
            الإصدار {config.app.version} - البيئة: {config.app.environment}
          </Text>
        </View>
      </ScrollView>
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
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    textAlign: 'center',
    marginBottom: 5,
  },
  headerSubtitle: {
    fontSize: 16,
    color: '#E3F2FD',
    textAlign: 'center',
    marginBottom: 10,
  },
  lastUpdated: {
    fontSize: 14,
    color: '#E3F2FD',
    textAlign: 'center',
  },
  content: {
    flex: 1,
    padding: 20,
  },
  section: {
    backgroundColor: '#fff',
    padding: 20,
    marginBottom: 15,
    borderRadius: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 10,
    textAlign: 'right',
  },
  subsectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
    marginTop: 10,
    marginBottom: 5,
    textAlign: 'right',
  },
  sectionText: {
    fontSize: 14,
    lineHeight: 22,
    color: '#444',
    textAlign: 'right',
    marginBottom: 10,
  },
  bulletPoint: {
    fontSize: 14,
    lineHeight: 20,
    color: '#444',
    textAlign: 'right',
    marginBottom: 5,
    paddingRight: 10,
  },
  warningText: {
    fontSize: 14,
    lineHeight: 20,
    color: '#FF6B35',
    textAlign: 'right',
    fontWeight: '600',
    backgroundColor: '#FFF3E0',
    padding: 10,
    borderRadius: 5,
    marginTop: 10,
  },
  contactInfo: {
    fontSize: 14,
    color: '#007AFF',
    textAlign: 'right',
    marginBottom: 5,
    fontWeight: '500',
  },
  actionsSection: {
    marginTop: 20,
    marginBottom: 20,
  },
  acceptButton: {
    backgroundColor: '#34C759',
    padding: 15,
    borderRadius: 10,
    marginBottom: 10,
    alignItems: 'center',
  },
  acceptButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  declineButton: {
    backgroundColor: '#FF3B30',
    padding: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  declineButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  footer: {
    marginTop: 30,
    paddingTop: 20,
    borderTopWidth: 1,
    borderTopColor: '#eee',
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: '#888',
    textAlign: 'center',
    marginBottom: 5,
  },
});