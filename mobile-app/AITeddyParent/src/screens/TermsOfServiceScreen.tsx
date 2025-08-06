/**
 * Terms of Service Screen - شروط الاستخدام
 * 
 * Features:
 * - Comprehensive terms and conditions
 * - Arabic language support
 * - Child safety focus
 * - Legal compliance
 * - User responsibilities
 * - Service limitations
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

interface TermsOfServiceScreenProps {
  onAccept?: () => void;
  onDecline?: () => void;
  showActions?: boolean;
}

export default function TermsOfServiceScreen({
  onAccept,
  onDecline,
  showActions = false,
}: TermsOfServiceScreenProps) {
  const handleAccept = () => {
    Alert.alert(
      'قبول شروط الاستخدام',
      'هل توافق على شروط الاستخدام وتتعهد بالالتزام بها؟',
      [
        { text: 'لا', style: 'cancel', onPress: onDecline },
        { text: 'نعم، أوافق', onPress: onAccept },
      ]
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>شروط الاستخدام</Text>
        <Text style={styles.headerSubtitle}>
          تطبيق AI Teddy Bear - مراقبة الوالدين
        </Text>
        <Text style={styles.lastUpdated}>
          آخر تحديث: {new Date().toLocaleDateString('ar')}
        </Text>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={true}>
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📋 مقدمة</Text>
          <Text style={styles.sectionText}>
            مرحباً بك في تطبيق AI Teddy Parent. هذه الشروط تحكم استخدامك للتطبيق والخدمات المرتبطة به. 
            باستخدام التطبيق، فإنك توافق على الالتزام بهذه الشروط وسياسة الخصوصية.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🎯 الغرض من الخدمة</Text>
          <Text style={styles.sectionText}>
            تطبيق AI Teddy Parent مصمم لتوفير:
          </Text>
          <Text style={styles.bulletPoint}>• مراقبة تفاعلات الأطفال مع الدب الذكي</Text>
          <Text style={styles.bulletPoint}>• تنبيهات الأمان الفورية</Text>
          <Text style={styles.bulletPoint}>• تقارير الاستخدام والتقدم</Text>
          <Text style={styles.bulletPoint}>• أدوات الرقابة الوالدية</Text>
          <Text style={styles.bulletPoint}>• إعدادات الأمان والخصوصية</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>👤 الأهلية للاستخدام</Text>
          <Text style={styles.sectionText}>لاستخدام هذا التطبيق، يجب أن تكون:</Text>
          <Text style={styles.bulletPoint}>• والد أو وصي قانوني للطفل</Text>
          <Text style={styles.bulletPoint}>• بعمر 18 سنة أو أكثر</Text>
          <Text style={styles.bulletPoint}>• مقيم في دولة مدعومة</Text>
          <Text style={styles.bulletPoint}>• قادر قانونياً على إبرام العقود</Text>
          
          <Text style={styles.warningText}>
            ⚠️ استخدام التطبيق من قبل أشخاص غير مؤهلين يعتبر انتهاكاً لهذه الشروط.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📱 تسجيل الحساب</Text>
          <Text style={styles.sectionText}>عند تسجيل حساب، تتعهد بما يلي:</Text>
          <Text style={styles.bulletPoint}>• تقديم معلومات صحيحة ومحدثة</Text>
          <Text style={styles.bulletPoint}>• الحفاظ على سرية كلمة المرور</Text>
          <Text style={styles.bulletPoint}>• إشعارنا فوراً بأي استخدام غير مصرح</Text>
          <Text style={styles.bulletPoint}>• تحديث المعلومات عند تغييرها</Text>
          <Text style={styles.bulletPoint}>• استخدام الحساب لأطفالك فقط</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>👪 مسؤوليات الوالدين</Text>
          <Text style={styles.sectionText}>كوالد أو وصي، أنت مسؤول عن:</Text>
          <Text style={styles.bulletPoint}>• الإشراف على استخدام الطفل للدب الذكي</Text>
          <Text style={styles.bulletPoint}>• مراجعة تقارير التفاعلات بانتظام</Text>
          <Text style={styles.bulletPoint}>• الاستجابة لتنبيهات الأمان فوراً</Text>
          <Text style={styles.bulletPoint}>• تعليم الطفل الاستخدام الآمن</Text>
          <Text style={styles.bulletPoint}>• تحديث إعدادات الأمان حسب الحاجة</Text>
          
          <Text style={styles.warningText}>
            🚨 تجاهل تنبيهات الأمان قد يعرض طفلك للخطر.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🚫 الاستخدام المحظور</Text>
          <Text style={styles.sectionText}>يُحظر استخدام التطبيق في:</Text>
          <Text style={styles.bulletPoint}>• مراقبة أطفال آخرين بدون إذن والديهم</Text>
          <Text style={styles.bulletPoint}>• انتهاك خصوصية الآخرين</Text>
          <Text style={styles.bulletPoint}>• محاولة اختراق أو تعطيل النظام</Text>
          <Text style={styles.bulletPoint}>• مشاركة بيانات الدخول مع الغير</Text>
          <Text style={styles.bulletPoint}>• استخدام التطبيق لأغراض تجارية</Text>
          <Text style={styles.bulletPoint}>• تحميل محتوى ضار أو غير قانوني</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🔐 أمان الأطفال</Text>
          <Text style={styles.sectionText}>
            نحن ملتزمون بحماية الأطفال من خلال:
          </Text>
          <Text style={styles.bulletPoint}>• مراقبة جميع التفاعلات في الوقت الفعلي</Text>
          <Text style={styles.bulletPoint}>• فلترة المحتوى غير المناسب</Text>
          <Text style={styles.bulletPoint}>• إرسال تنبيهات فورية للمخاطر</Text>
          <Text style={styles.bulletPoint}>• حفظ سجلات للمراجعة الوالدية</Text>
          <Text style={styles.bulletPoint}>• منع التفاعلات الضارة</Text>
          
          <Text style={styles.sectionText}>
            ولكن، نحن لا نضمن منع جميع المخاطر المحتملة، ويبقى الإشراف الوالدي ضرورياً.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>💰 الرسوم والاشتراكات</Text>
          <Text style={styles.bulletPoint}>• التطبيق يتطلب اشتراك شهري أو سنوي</Text>
          <Text style={styles.bulletPoint}>• الرسوم قابلة للتغيير بإشعار مسبق</Text>
          <Text style={styles.bulletPoint}>• لا توجد استردادات للفترات المستخدمة</Text>
          <Text style={styles.bulletPoint}>• التجديد تلقائي ما لم يتم الإلغاء</Text>
          <Text style={styles.bulletPoint}>• توقف الخدمة عند عدم الدفع</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📊 استخدام البيانات</Text>
          <Text style={styles.sectionText}>
            نستخدم البيانات المجمعة لتحسين الخدمة من خلال:
          </Text>
          <Text style={styles.bulletPoint}>• تطوير خوارزميات الأمان</Text>
          <Text style={styles.bulletPoint}>• تحسين دقة فلترة المحتوى</Text>
          <Text style={styles.bulletPoint}>• إنتاج تقارير إحصائية مجهولة</Text>
          <Text style={styles.bulletPoint}>• البحث والتطوير في أمان الأطفال</Text>
          
          <Text style={styles.warningText}>
            🔒 جميع البيانات الشخصية محمية وفقاً لسياسة الخصوصية.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🚨 حالات الطوارئ</Text>
          <Text style={styles.sectionText}>
            في حالات الطوارئ التي تهدد سلامة الطفل، نحتفظ بالحق في:
          </Text>
          <Text style={styles.bulletPoint}>• إيقاف التفاعل مع الدب فوراً</Text>
          <Text style={styles.bulletPoint}>• إشعار الوالدين والسلطات المختصة</Text>
          <Text style={styles.bulletPoint}>• حفظ سجلات التفاعل للتحقيق</Text>
          <Text style={styles.bulletPoint}>• التعاون مع جهات إنفاذ القانون</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>⚡ انقطاع الخدمة</Text>
          <Text style={styles.sectionText}>
            قد تتعرض الخدمة لانقطاع مؤقت بسبب:
          </Text>
          <Text style={styles.bulletPoint}>• صيانة مجدولة أو طارئة</Text>
          <Text style={styles.bulletPoint}>• مشاكل تقنية أو شبكة</Text>
          <Text style={styles.bulletPoint}>• تحديثات أمنية مهمة</Text>
          <Text style={styles.bulletPoint}>• ظروف خارجة عن سيطرتنا</Text>
          
          <Text style={styles.sectionText}>
            سنبذل قصارى جهدنا لتقليل انقطاع الخدمة وإشعارك مسبقاً عند الإمكان.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🛡️ حدود المسؤولية</Text>
          <Text style={styles.sectionText}>
            مسؤوليتنا محدودة بالحد الأقصى المسموح قانونياً، ونحن غير مسؤولين عن:
          </Text>
          <Text style={styles.bulletPoint}>• أضرار غير مباشرة أو عرضية</Text>
          <Text style={styles.bulletPoint}>• فقدان البيانات بسبب عطل تقني</Text>
          <Text style={styles.bulletPoint}>• تصرفات أطراف ثالثة</Text>
          <Text style={styles.bulletPoint}>• سوء استخدام التطبيق من قبل المستخدم</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🔄 تعديل الشروط</Text>
          <Text style={styles.sectionText}>
            نحتفظ بالحق في تعديل هذه الشروط في أي وقت. التعديلات الجوهرية ستكون مع:
          </Text>
          <Text style={styles.bulletPoint}>• إشعار مسبق 30 يوماً</Text>
          <Text style={styles.bulletPoint}>• بريد إلكتروني للمستخدمين</Text>
          <Text style={styles.bulletPoint}>• إشعار داخل التطبيق</Text>
          <Text style={styles.bulletPoint}>• تحديث تاريخ "آخر تحديث"</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🏛️ القانون المطبق</Text>
          <Text style={styles.sectionText}>
            هذه الشروط محكومة بقوانين المملكة العربية السعودية. أي نزاع سيخضع لاختصاص المحاكم السعودية.
          </Text>
          
          <Text style={styles.sectionText}>
            كما نلتزم بالقوانين الدولية ذات الصلة:
          </Text>
          <Text style={styles.bulletPoint}>• قانون COPPA الأمريكي</Text>
          <Text style={styles.bulletPoint}>• لائحة GDPR الأوروبية</Text>
          <Text style={styles.bulletPoint}>• معايير ISO/IEC 27001</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📞 التواصل</Text>
          <Text style={styles.sectionText}>
            للاستفسارات حول هذه الشروط أو الخدمة:
          </Text>
          <Text style={styles.contactInfo}>📧 البريد الإلكتروني: support@aiteddybear.com</Text>
          <Text style={styles.contactInfo}>📞 الدعم الفني: +966-50-123-4567</Text>
          <Text style={styles.contactInfo}>⚖️ الشؤون القانونية: legal@aiteddybear.com</Text>
          <Text style={styles.contactInfo}>📍 العنوان: الرياض، المملكة العربية السعودية</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>✅ إقرار وموافقة</Text>
          <Text style={styles.warningText}>
            باستخدام التطبيق، تقر وتوافق على:
            • فهم هذه الشروط والالتزام بها
            • كونك والد أو وصي قانوني للطفل
            • الإشراف المسؤول على استخدام الطفل
            • الاستجابة لتنبيهات الأمان فوراً
            • احترام خصوصية الآخرين وحقوقهم
          </Text>
        </View>

        {showActions && (
          <View style={styles.actionsSection}>
            <TouchableOpacity style={styles.acceptButton} onPress={handleAccept}>
              <Text style={styles.acceptButtonText}>✅ أوافق على شروط الاستخدام</Text>
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
          <Text style={styles.footerText}>
            للاستخدام الوالدي فقط - غير مخصص للأطفال
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
    backgroundColor: '#FF6B35',
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
    color: '#FFE5D9',
    textAlign: 'center',
    marginBottom: 10,
  },
  lastUpdated: {
    fontSize: 14,
    color: '#FFE5D9',
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
    color: '#D32F2F',
    textAlign: 'right',
    fontWeight: '600',
    backgroundColor: '#FFEBEE',
    padding: 10,
    borderRadius: 5,
    marginTop: 10,
    borderLeftWidth: 4,
    borderLeftColor: '#D32F2F',
  },
  contactInfo: {
    fontSize: 14,
    color: '#FF6B35',
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