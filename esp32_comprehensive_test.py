#!/usr/bin/env python3
"""
فحص شامل لطلبات ESP32 - AI Teddy Bear
=====================================
سكريبت شامل لفحص جميع endpoints الخاصة بـ ESP32 والتأكد من عملها
"""

import requests
import json
import hashlib
import hmac
import secrets
import time
import sys
import asyncio
import websockets
from datetime import datetime
from typing import Dict, Any, Optional
import logging

# إعداد السيرفر
BASE_URL = "http://127.0.0.1:8000"  # تأكد من البورت الصحيح
WS_URL = "ws://127.0.0.1:8000"

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ESP32Tester:
    """فئة شاملة لفحص جميع طلبات ESP32"""
    
    def __init__(self, base_url: str = BASE_URL, ws_url: str = WS_URL):
        self.base_url = base_url
        self.ws_url = ws_url
        self.session = requests.Session()
        self.session.timeout = 30
        self.results = {}
        
    def generate_device_oob_secret(self, device_id: str) -> str:
        """توليد OOB secret للجهاز (يطابق منطق السيرفر)"""
        salt = "ai-teddy-bear-oob-secret-v1"
        hash_input = f"{device_id}:{salt}".encode('utf-8')
        
        device_hash = hashlib.sha256(hash_input).hexdigest()
        final_hash = hashlib.sha256((device_hash + salt).encode('utf-8')).hexdigest()
        
        return final_hash.upper()
    
    def generate_test_hmac(self, device_id: str, child_id: str, nonce: str, oob_secret: str) -> str:
        """توليد HMAC للمصادقة"""
        oob_secret_bytes = bytes.fromhex(oob_secret)
        mac = hmac.new(oob_secret_bytes, digestmod=hashlib.sha256)
        
        mac.update(device_id.encode('utf-8'))
        mac.update(child_id.encode('utf-8'))
        mac.update(bytes.fromhex(nonce))
        
        return mac.hexdigest()
    
    def test_health_endpoint(self) -> bool:
        """فحص endpoint الصحة العامة"""
        print("🔍 فحص endpoint الصحة العامة...")
        try:
            response = self.session.get(f"{self.base_url}/health")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ السيرفر يعمل - الحالة: {data.get('status', 'unknown')}")
                print(f"   📊 البيئة: {data.get('environment', 'unknown')}")
                self.results['health'] = True
                return True
            else:
                print(f"   ❌ فشل فحص الصحة - كود الحالة: {response.status_code}")
                print(f"   📝 الرد: {response.text}")
                self.results['health'] = False
                return False
                
        except Exception as e:
            print(f"   ❌ خطأ في فحص الصحة: {e}")
            self.results['health'] = False
            return False
    
    def test_esp32_config_endpoint(self) -> bool:
        """فحص endpoint إعدادات ESP32"""
        print("🔧 فحص endpoint إعدادات ESP32...")
        try:
            response = self.session.get(f"{self.base_url}/api/v1/esp32/config")
            
            if response.status_code == 200:
                config = response.json()
                print(f"   ✅ إعدادات ESP32 متاحة")
                print(f"   🌐 المضيف: {config.get('host', 'غير محدد')}")
                print(f"   🔌 البورت: {config.get('port', 'غير محدد')}")
                print(f"   📡 مسار WebSocket: {config.get('ws_path', 'غير محدد')}")
                print(f"   🔒 TLS: {config.get('tls', False)}")
                print(f"   📱 إصدار التطبيق: {config.get('app_version', 'غير محدد')}")
                print(f"   💾 إصدار الفيرموير: {config.get('firmware_version', 'غير محدد')}")
                
                # فحص الميزات
                features = config.get('features', {})
                print(f"   🚀 الميزات المتاحة:")
                for feature, enabled in features.items():
                    status = "✅" if enabled else "❌"
                    print(f"      {status} {feature}: {enabled}")
                
                self.results['esp32_config'] = True
                return True
            else:
                print(f"   ❌ فشل الحصول على إعدادات ESP32 - كود الحالة: {response.status_code}")
                print(f"   📝 الرد: {response.text}")
                self.results['esp32_config'] = False
                return False
                
        except Exception as e:
            print(f"   ❌ خطأ في فحص إعدادات ESP32: {e}")
            self.results['esp32_config'] = False
            return False
    
    def test_esp32_firmware_endpoint(self) -> bool:
        """فحص endpoint الفيرموير"""
        print("💾 فحص endpoint الفيرموير...")
        try:
            response = self.session.get(f"{self.base_url}/api/v1/esp32/firmware")
            
            if response.status_code == 200:
                firmware = response.json()
                print(f"   ✅ معلومات الفيرموير متاحة")
                print(f"   📦 الإصدار: {firmware.get('version', 'غير محدد')}")
                print(f"   📏 الحجم: {firmware.get('size', 0):,} بايت")
                print(f"   🔐 SHA256: {firmware.get('sha256', 'غير محدد')[:16]}...")
                print(f"   🌐 رابط التنزيل: {firmware.get('url', 'غير محدد')}")
                print(f"   ✅ متاح: {firmware.get('available', False)}")
                print(f"   ⚠️ إجباري: {firmware.get('mandatory', False)}")
                
                # فحص التوافق
                compatibility = firmware.get('compatibility', {})
                if compatibility:
                    print(f"   🔧 التوافق:")
                    print(f"      📱 أدنى إصدار هاردوير: {compatibility.get('min_hardware_version', 'غير محدد')}")
                    print(f"      📱 أعلى إصدار هاردوير: {compatibility.get('max_hardware_version', 'غير محدد')}")
                    print(f"      🚀 Bootloader مطلوب: {compatibility.get('required_bootloader', 'غير محدد')}")
                
                # فحص البيانات الوصفية
                meta = firmware.get('meta', {})
                if meta:
                    print(f"   📊 البيانات الوصفية:")
                    print(f"      📁 الملف موجود: {meta.get('file_exists', False)}")
                    print(f"      ✅ تم التحقق: {meta.get('validated', False)}")
                
                self.results['esp32_firmware'] = True
                return True
            elif response.status_code == 404:
                print(f"   ⚠️ الفيرموير غير متاح حالياً (404)")
                self.results['esp32_firmware'] = False
                return False
            elif response.status_code == 503:
                print(f"   ⚠️ خدمة الفيرموير غير متاحة مؤقتاً (503)")
                self.results['esp32_firmware'] = False
                return False
            else:
                print(f"   ❌ فشل الحصول على معلومات الفيرموير - كود الحالة: {response.status_code}")
                print(f"   📝 الرد: {response.text}")
                self.results['esp32_firmware'] = False
                return False
                
        except Exception as e:
            print(f"   ❌ خطأ في فحص الفيرموير: {e}")
            self.results['esp32_firmware'] = False
            return False
    
    def test_esp32_claim_endpoint(self) -> Optional[Dict[str, Any]]:
        """فحص endpoint ربط الجهاز"""
        print("🔗 فحص endpoint ربط الجهاز...")
        
        # بيانات الاختبار
        device_id = "Teddy-ESP32-TEST001"
        child_id = "test-child-456"
        nonce = secrets.token_hex(16)
        
        # توليد OOB secret و HMAC
        oob_secret = self.generate_device_oob_secret(device_id)
        hmac_signature = self.generate_test_hmac(device_id, child_id, nonce, oob_secret)
        
        payload = {
            "device_id": device_id,
            "child_id": child_id,
            "nonce": nonce,
            "hmac_hex": hmac_signature,
            "firmware_version": "1.2.1"
        }
        
        print(f"   📱 الجهاز: {device_id}")
        print(f"   👶 الطفل: {child_id}")
        print(f"   🔢 Nonce: {nonce[:16]}...")
        print(f"   🔐 HMAC: {hmac_signature[:16]}...")
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/pair/claim",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"   📊 كود الحالة: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("   ✅ تم ربط الجهاز بنجاح!")
                print(f"   🎫 Token: {data.get('access_token', '')[:20]}...")
                print(f"   🔑 Session ID: {data.get('device_session_id', 'غير محدد')}")
                print(f"   ⏰ انتهاء الصلاحية: {data.get('expires_in', 'غير محدد')} ثانية")
                self.results['esp32_claim'] = True
                return data
            elif response.status_code == 404:
                print("   ⚠️ ملف الطفل غير موجود (متوقع في بيئة الاختبار)")
                self.results['esp32_claim'] = False
                return None
            elif response.status_code == 503:
                print("   ⚠️ الخدمة لا تزال في مرحلة التهيئة")
                self.results['esp32_claim'] = False
                return None
            elif response.status_code == 400:
                print(f"   ❌ بيانات غير صحيحة: {response.text}")
                self.results['esp32_claim'] = False
                return None
            elif response.status_code == 403:
                print(f"   ❌ مصادقة فاشلة: {response.text}")
                self.results['esp32_claim'] = False
                return None
            else:
                print(f"   ❌ فشل ربط الجهاز: {response.text}")
                self.results['esp32_claim'] = False
                return None
                
        except Exception as e:
            print(f"   ❌ خطأ في ربط الجهاز: {e}")
            self.results['esp32_claim'] = False
            return None
    
    def test_esp32_metrics_endpoint(self, token: Optional[str] = None) -> bool:
        """فحص endpoint المقاييس (يتطلب مصادقة)"""
        print("📊 فحص endpoint المقاييس...")
        
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            headers["Authorization"] = "Bearer dummy-token-for-testing"
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/esp32/metrics",
                headers=headers
            )
            
            print(f"   📊 كود الحالة: {response.status_code}")
            
            if response.status_code == 200:
                metrics = response.json()
                print("   ✅ المقاييس متاحة!")
                print(f"   📈 البيانات: {json.dumps(metrics, indent=2, ensure_ascii=False)}")
                self.results['esp32_metrics'] = True
                return True
            elif response.status_code == 401:
                print("   ⚠️ مطلوب مصادقة (متوقع)")
                self.results['esp32_metrics'] = False
                return False
            elif response.status_code == 403:
                print("   ⚠️ غير مخول للوصول")
                self.results['esp32_metrics'] = False
                return False
            else:
                print(f"   ❌ فشل الحصول على المقاييس: {response.text}")
                self.results['esp32_metrics'] = False
                return False
                
        except Exception as e:
            print(f"   ❌ خطأ في فحص المقاييس: {e}")
            self.results['esp32_metrics'] = False
            return False
    
    async def test_esp32_websocket(self, token: Optional[str] = None) -> bool:
        """فحص WebSocket للدردشة"""
        print("💬 فحص WebSocket للدردشة...")
        
        # بيانات الاختبار
        device_id = "Teddy-ESP32-WS001"
        child_id = "test-child-ws"
        child_name = "أحمد"
        child_age = 7
        
        # إعداد المعاملات
        params = {
            "device_id": device_id,
            "child_id": child_id,
            "child_name": child_name,
            "child_age": child_age
        }
        
        if token:
            params["token"] = token
        else:
            # توليد token تجريبي
            params["token"] = "test-token-" + secrets.token_hex(16)
        
        # بناء URL
        ws_url = f"{self.ws_url}/api/v1/esp32/chat"
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        full_ws_url = f"{ws_url}?{query_string}"
        
        print(f"   🌐 الاتصال بـ: {full_ws_url}")
        
        try:
            # محاولة الاتصال بـ WebSocket
            async with websockets.connect(full_ws_url, timeout=10) as websocket:
                print("   ✅ تم الاتصال بـ WebSocket!")
                
                # إرسال رسالة اختبار
                test_message = {
                    "type": "text_message",
                    "data": {
                        "text": "مرحبا، هذه رسالة اختبار"
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(test_message, ensure_ascii=False))
                print("   📤 تم إرسال رسالة اختبار")
                
                # انتظار الرد (مع timeout)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    print(f"   📥 تم استلام رد: {response[:100]}...")
                    self.results['esp32_websocket'] = True
                    return True
                except asyncio.TimeoutError:
                    print("   ⏰ انتهت مهلة انتظار الرد")
                    self.results['esp32_websocket'] = False
                    return False
                    
        except websockets.exceptions.ConnectionClosed as e:
            print(f"   ❌ تم إغلاق الاتصال: {e}")
            self.results['esp32_websocket'] = False
            return False
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 403:
                print("   ⚠️ مطلوب مصادقة صحيحة للـ WebSocket")
            elif e.status_code == 400:
                print("   ❌ معاملات غير صحيحة")
            else:
                print(f"   ❌ كود حالة غير صحيح: {e.status_code}")
            self.results['esp32_websocket'] = False
            return False
        except Exception as e:
            print(f"   ❌ خطأ في WebSocket: {e}")
            self.results['esp32_websocket'] = False
            return False
    
    def test_routes_health(self) -> bool:
        """فحص صحة الراوترات"""
        print("🛣️ فحص صحة الراوترات...")
        try:
            response = self.session.get(f"{self.base_url}/routes-health")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ صحة الراوترات: {data.get('status', 'unknown')}")
                
                route_system = data.get('route_system', {})
                if route_system:
                    print(f"   📊 إجمالي الراوترات: {route_system.get('total_routes', 0)}")
                    print(f"   🔍 حالة الراوترات: {route_system.get('route_health', 'unknown')}")
                    print(f"   📈 المراقبة مفعلة: {route_system.get('monitoring_enabled', False)}")
                
                self.results['routes_health'] = True
                return True
            else:
                print(f"   ❌ فشل فحص صحة الراوترات - كود الحالة: {response.status_code}")
                self.results['routes_health'] = False
                return False
                
        except Exception as e:
            print(f"   ❌ خطأ في فحص صحة الراوترات: {e}")
            self.results['routes_health'] = False
            return False
    
    def print_summary(self):
        """طباعة ملخص النتائج"""
        print("\n" + "="*60)
        print("📋 ملخص نتائج فحص ESP32")
        print("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(self.results.values())
        
        for test_name, passed in self.results.items():
            status = "✅ نجح" if passed else "❌ فشل"
            test_name_ar = {
                'health': 'فحص الصحة العامة',
                'esp32_config': 'إعدادات ESP32',
                'esp32_firmware': 'معلومات الفيرموير',
                'esp32_claim': 'ربط الجهاز',
                'esp32_metrics': 'المقاييس',
                'esp32_websocket': 'WebSocket للدردشة',
                'routes_health': 'صحة الراوترات'
            }.get(test_name, test_name)
            
            print(f"   {status} {test_name_ar}")
        
        print(f"\n📊 النتيجة النهائية: {passed_tests}/{total_tests} اختبار نجح")
        
        if passed_tests == total_tests:
            print("🎉 جميع الاختبارات نجحت! ESP32 يعمل بشكل مثالي.")
            return 0
        elif passed_tests >= total_tests * 0.7:
            print("⚠️ معظم الاختبارات نجحت، لكن هناك بعض المشاكل.")
            return 1
        else:
            print("❌ فشلت معظم الاختبارات. تحقق من السيرفر والإعدادات.")
            return 2

async def main():
    """الدالة الرئيسية"""
    print("🤖 AI Teddy Bear - فحص شامل لطلبات ESP32")
    print("="*60)
    print(f"🌐 السيرفر: {BASE_URL}")
    print(f"📡 WebSocket: {WS_URL}")
    print()
    
    tester = ESP32Tester()
    
    # تشغيل الاختبارات بالتسلسل
    print("🚀 بدء الاختبارات...")
    print()
    
    # 1. فحص الصحة العامة
    health_ok = tester.test_health_endpoint()
    print()
    
    if not health_ok:
        print("❌ السيرفر لا يعمل. توقف الاختبارات.")
        return 2
    
    # 2. فحص صحة الراوترات
    tester.test_routes_health()
    print()
    
    # 3. فحص إعدادات ESP32
    tester.test_esp32_config_endpoint()
    print()
    
    # 4. فحص الفيرموير
    tester.test_esp32_firmware_endpoint()
    print()
    
    # 5. فحص ربط الجهاز
    claim_result = tester.test_esp32_claim_endpoint()
    token = claim_result.get('access_token') if claim_result else None
    print()
    
    # 6. فحص المقاييس
    tester.test_esp32_metrics_endpoint(token)
    print()
    
    # 7. فحص WebSocket
    await tester.test_esp32_websocket(token)
    print()
    
    # طباعة الملخص
    return tester.print_summary()

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️ تم إيقاف الاختبارات بواسطة المستخدم")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ خطأ غير متوقع: {e}")
        sys.exit(2)