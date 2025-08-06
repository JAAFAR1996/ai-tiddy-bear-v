/**
 * 🔧 Development Test Credentials
 * بيانات اختبار بسيطة للتطوير فقط
 */

// ⚠️ هذه البيانات للتطوير فقط - لا تستخدم في الإنتاج
export const DEV_CREDENTIALS = {
  // بيانات تسجيل دخول بسيطة للاختبار
  email: 'test@test.com',
  password: '123456',
  
  // بديل أبسط
  simpleEmail: 'a@a.com',
  simplePassword: '123',
  
  // بيانات إضافية للاختبار
  parentName: 'Test Parent',
  childName: 'Test Child',
};

// دالة للحصول على بيانات الاختبار
export const getTestCredentials = () => {
  // تحقق من أن البيئة للتطوير فقط
  if (__DEV__) {
    return DEV_CREDENTIALS;
  }
  
  // في الإنتاج، لا ترجع أي بيانات اختبار
  return null;
};

// نصائح للمطور
export const DEVELOPER_NOTES = `
🔧 بيانات الاختبار المبسطة:

الإيميل: test@test.com أو a@a.com
كلمة المرور: 123456 أو 123

هذه البيانات مخصصة للتطوير والاختبار فقط.
في الإنتاج، يجب استخدام بيانات حقيقية وآمنة.

للاختبار السريع:
- استخدم a@a.com مع 123 
- أو test@test.com مع 123456
`;

export default DEV_CREDENTIALS;
