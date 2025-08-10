/*
 * ESP32 SSL Configuration Example for AI Teddy Bear
 * Supports both esp_crt_bundle and manual certificate loading
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <esp_crt_bundle.h>

// Network credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Server configuration - FIXED DOMAIN NAME
const char* serverHost = "ai-tiddy-bear-v.onrender.com";  // الدومين الصحيح مع tiddy وليس teddy
const int serverPort = 443;
const char* configEndpoint = "/api/esp32/config";
const char* firmwareEndpoint = "/api/esp32/firmware";
const char* websocketPath = "/ws/esp32/connect";

// Certificate bundle (if using manual certificates)
const char* root_ca_pem = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFVzCCAz+gAwIBAgINAgPlk28xsBNJiGuiFzANBgkqhkiG9w0BAQwFADCBkDEL
MAkGA1UEBhMCR0IxGzAZBgNVBAgTEkdyZWF0ZXIgTWFuY2hlc3RlcjEQMA4GA1UE
BxMHU2FsZm9yZDEaMBgGA1UEChMRQ09NT0RPIENBIExpbWl0ZWQxNjA0BgNVBAMT
LUNPTU9ETyBSU0EgQ2VydGlmaWNhdGlvbiBBdXRob3JpdHkwHhcNMTQwMjEyMDAw
MDAwWhcNMjkwMjExMjM1OTU5WjCBkDELMAkGA1UEBhMCR0IxGzAZBgNVBAgTEkdy
ZWF0ZXIgTWFuY2hlc3RlcjEQMA4GA1UEBxMHU2FsZm9yZDEaMBgGA1UEChMRQ09N
T0RPIENBIExpbWl0ZWQxNjA4BgNVBAMTLUNPTU9ETyBSU0EgQ2VydGlmaWNhdGlv
biBBdXRob3JpdHkwggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQCR6FSS
0gpWsawNJN3Fz0RndJkrN6N9I3AAcbxT38T6KhKPS38QVr2fcHK3YX/JSw8Xpz3j
sARh7v8Rl8f0hj4K+j5c+ZPmNHrZFGvnnLOFoIJ6dq9xkNfs/Q36nGz637CC9BR+
b4HcDu4uIuW/pkvY7uOOW5l0tlnXLpsVrSs3GyS2SMkRfI5mjq4Ub8EQs7zKyxWO
uBB42tE3Xyx5j6z3pqm2m6XuWtXvIEv0JvQDhJXdF0zLmm4IZOhmz8hVWP7qllqZ
d4J1jdMZiTnhWz4JcOLdJhbv7J6IzLXSdOnNzc2NkgGkLHYc+6z30mXFo4OE9U1T
6fJRN2cWFdQIJh0/yGk6jMvekOK0nfKslYBBhSWMfYI6yc4kQCq4n4zJN5qSEhKi
qRGjDDOXLmBx37+p5OzI6ZwFpV/pUNLHOkLBQVGEBqg7k7YUq1fEDRPX+VHqMTpF
C4UZgxlLj8FWt3X9VVrNgdqzAQHVi7T6nR0xqGjdGSrILm/4NTEYzUFKWPEPJBNi
XxXGgN4wETM4N2L/jRnXjZXoO9rTdKJr0Nzs6a8rXs5mXgJf7rEOxGZILjEaJhVy
nTLp4XJy4wvQNdQxJQWnxJmqRZeYsZhAHJ1SBZ6WPuVY6kUjY6FaQ/YUqh0Jv3Ww
Xe1T5pM2VYVqNUf/uJgBGXP4zQ2qFWHpF6EfZAQHEDFYa8VUuSkz5rRCJOpF
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC
jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc
oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq
4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA
mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d
emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----
)EOF";

void setup() {
  Serial.begin(115200);
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("WiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  
  // Test SSL connection
  testSSLConnection();
}

void loop() {
  // Main loop
  delay(10000);
}

// METHOD 1: استخدام esp_crt_bundle_attach (الطريقة الأفضل)
void testSSLWithBundle() {
  WiFiClientSecure client;
  
  // استخدم Mozilla CA bundle المدمج
  client.setCACertBundle(esp_crt_bundle_attach);
  
  // تعيين SNI
  client.setInsecure(false);  // تأكد من التحقق من الشهادة
  
  Serial.println("[BUNDLE] Testing SSL connection with Mozilla CA bundle...");
  
  if (client.connect(serverHost, serverPort)) {
    Serial.println("[BUNDLE] ✅ SSL connection successful!");
    
    // إرسال طلب HTTP
    String request = "GET " + String(configEndpoint) + " HTTP/1.1\r\n";
    request += "Host: " + String(serverHost) + "\r\n";
    request += "User-Agent: ESP32-TeddyBear/1.0\r\n";
    request += "Connection: close\r\n\r\n";
    
    client.print(request);
    
    // قراءة الاستجابة
    while (client.connected() && client.available()) {
      String line = client.readStringUntil('\n');
      Serial.println("[BUNDLE] " + line);
      if (line.indexOf("ws_path") > -1) {
        Serial.println("[BUNDLE] ✅ Config endpoint working!");
        break;
      }
    }
    client.stop();
  } else {
    Serial.println("[BUNDLE] ❌ SSL connection failed!");
  }
}

// METHOD 2: استخدام الشهادات اليدوية
void testSSLWithManualCerts() {
  WiFiClientSecure client;
  
  // استخدم الشهادات اليدوية
  client.setCACert(root_ca_pem);
  
  Serial.println("[MANUAL] Testing SSL connection with manual certificates...");
  
  if (client.connect(serverHost, serverPort)) {
    Serial.println("[MANUAL] ✅ SSL connection successful!");
    
    // إرسال طلب HTTP
    String request = "GET " + String(firmwareEndpoint) + " HTTP/1.1\r\n";
    request += "Host: " + String(serverHost) + "\r\n";
    request += "User-Agent: ESP32-TeddyBear/1.0\r\n";
    request += "Connection: close\r\n\r\n";
    
    client.print(request);
    
    // قراءة الاستجابة
    while (client.connected() && client.available()) {
      String line = client.readStringUntil('\n');
      Serial.println("[MANUAL] " + line);
      if (line.indexOf("version") > -1) {
        Serial.println("[MANUAL] ✅ Firmware endpoint working!");
        break;
      }
    }
    client.stop();
  } else {
    Serial.println("[MANUAL] ❌ SSL connection failed!");
  }
}

// METHOD 3: استخدام HTTPClient مع التحقق التلقائي
void testHTTPSClient() {
  HTTPClient https;
  
  // استخدم Mozilla CA bundle
  WiFiClientSecure client;
  client.setCACertBundle(esp_crt_bundle_attach);
  
  https.begin(client, "https://" + String(serverHost) + configEndpoint);
  https.addHeader("User-Agent", "ESP32-TeddyBear/1.0");
  
  Serial.println("[HTTPS] Testing HTTPS client...");
  
  int httpCode = https.GET();
  if (httpCode > 0) {
    Serial.printf("[HTTPS] ✅ HTTP response: %d\n", httpCode);
    
    if (httpCode == HTTP_CODE_OK) {
      String payload = https.getString();
      Serial.println("[HTTPS] Response:");
      Serial.println(payload);
    }
  } else {
    Serial.printf("[HTTPS] ❌ HTTP request failed: %s\n", https.errorToString(httpCode).c_str());
  }
  
  https.end();
}

void testSSLConnection() {
  Serial.println("=== ESP32 SSL Connection Tests ===");
  
  // تجربة الطرق الثلاث
  testSSLWithBundle();      // الطريقة الأفضل
  delay(2000);
  
  testSSLWithManualCerts(); // النسخة الاحتياطية
  delay(2000);
  
  testHTTPSClient();        // طريقة HTTPClient
  delay(2000);
  
  Serial.println("=== Tests completed ===");
}

// دالة مساعدة للتحقق من صحة الدومين
bool validateDomain(const char* domain) {
  // تحقق من الدومين الصحيح
  if (strstr(domain, "ai-tiddy-bear-v.onrender.com") == nullptr) {
    Serial.println("⚠️ WARNING: Domain should be 'ai-tiddy-bear-v.onrender.com'");
    return false;
  }
  
  if (strstr(domain, "onrender.com") == nullptr) {
    Serial.println("⚠️ WARNING: Domain doesn't contain 'onrender.com'");
    return false;
  }
  
  return true;
}