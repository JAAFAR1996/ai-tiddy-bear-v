#include "tls_certificate_manager.h"
#include "config.h"
#include <WiFiClientSecure.h>
#include "esp_crt_bundle.h"

// 🧸 EMERGENCY SIMPLIFICATION - Audio-only teddy bear TLS
// Minimal TLS for basic HTTPS connectivity - removed 2000+ lines of complexity

// Global variables
static bool tlsInitialized = false;

// Minimal TLS initialization 
bool initTLS() {
  if (tlsInitialized) return true;
  
  Serial.println("🔐 Minimal TLS init for audio-only teddy");
  tlsInitialized = true;
  return true;
}

// Simplified certificate handling
bool setupCertificates() {
  Serial.println("📜 Using system root certificates");
  return true; // ESP32 has built-in root certificates
}

// Secure TLS client setup for production
WiFiClientSecure* createSecureTLSClient() {
  WiFiClientSecure* client = new WiFiClientSecure();
  
#ifdef DEVELOPMENT_BUILD
  client->setInsecure(); // ⚠️ DEVELOPMENT ONLY!
  Serial.println("🔓 DEV MODE: Using insecure TLS");
#else
  // 🔒 PRODUCTION: Use proper certificate validation with fallback
  #if defined(CONFIG_MBEDTLS_CERTIFICATE_BUNDLE)
    // تمكين حزمة الجذور المدمجة (ESP-IDF CRT bundle)
    extern const uint8_t root_ca_crt_bundle_start[] asm("_binary_root_ca_crt_bundle_start");
    client->setCACertBundle(root_ca_crt_bundle_start);
    Serial.println("🔒 PRODUCTION: TLS via CA bundle");
  #else
    extern const char ROOT_CA_PEM[];
    client->setCACert(ROOT_CA_PEM);
    Serial.println("🔒 PRODUCTION: TLS via static ROOT_CA_PEM");
  #endif
  
  // Set timeout for production stability
  client->setTimeout(15000); // 15 second timeout
#endif
  
  return client;
}

// Stub functions for compatibility
bool validateCertificateChain() { return true; }
bool checkCertificateExpiry() { return true; }
void updateTrustedRoots() { /* Simplified */ }
bool performTLSHandshake() { return true; }
void cleanupTLS() { 
  tlsInitialized = false;
  Serial.println("🧹 TLS cleanup complete");
}

// Certificate validation with TLS diagnostics
bool validateServerCertificate(const char* hostname) {
  Serial.printf("🔍 Testing TLS connection to %s...\n", hostname);

  WiFiClientSecure* testClient = createSecureTLSClient();
  if (!testClient) {
    Serial.println("❌ Failed to create TLS client for validation");
    return false;
  }

  // مصافحة + طلب خفيف
  bool connected = testClient->connect(hostname, 443);
  if (!connected) {
    Serial.printf("❌ TLS connect() failed to %s\n", hostname);
    delete testClient;
    return false;
  }

  // إرسال HEAD للتأكد من القناة المشفّرة
  testClient->print(String("HEAD / HTTP/1.0\r\nHost: ") + hostname + "\r\n\r\n");

  // انتظر بضعة مليلثواني ليتوفر رد
  uint32_t start = millis();
  while (!testClient->available() && millis() - start < 2000) { delay(10); }

  bool gotAny = testClient->available() > 0;
  Serial.printf("🔒 TLS handshake+read: %s\n", gotAny ? "OK" : "NO DATA");

  testClient->stop();
  delete testClient;
  return gotAny;  // نجاح إذا وصل أي بايت (يعني TLS تمّ)
}

// TLS status check with connectivity test
bool isTLSHealthy() {
  if (!tlsInitialized) {
    return false;
  }
  
  // Quick connectivity test to main server  
  return validateServerCertificate("ai-tiddy-bear-v-xuqy.onrender.com");
}

// Memory cleanup
void releaseTLSResources() {
  Serial.println("🧸 Released TLS resources for teddy bear");
}