#include "security.h"
#include "monitoring.h"
#include "config.h"
#include "hardware.h"
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <SPIFFS.h>

// Global security variables
SecurityConfig securityConfig;
AuthStatus currentAuthStatus = AUTH_NONE;
unsigned long lastSecurityCheck = 0;
int authRetryCount = 0;

// Root CA certificate for production server
const char* ROOT_CA_CERT = R"EOF(
-----BEGIN CERTIFICATE-----
MIIDSjCCAjKgAwIBAgIQRK+wgNajJ7qJMDmGLvhAazANBgkqhkiG9w0BAQUFADA/
MSQwIgYDVQQKExtEaWdpdGFsIFNpZ25hdHVyZSBUcnVzdCBDby4xFzAVBgNVBAMT
DkRTVCBSb290IENBIFgzMB4XDTAwMDkzMDIxMTIxOVoXDTIxMDkzMDE0MDExNVow
PzEkMCIGA1UEChMbRGlnaXRhbCBTaWduYXR1cmUgVHJ1c3QgQ28uMRcwFQYDVQQD
Ew5EU1QgUm9vdCBDQSBYMzCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEB
AN+v6ZdQCINXtMxiZfaQguzH0yxrMMpb7NnDfcdAwRgUi+DoM3ZJKuM/IUmTrE4O
rz5Iy2Xu/NMhD2XSKtkyj4zl93ewEnu1lcCJo6m67XMuegwGMoOifooUMM0RoOEq
OLl5CjH9UL2AZd+3UWODyOKIYepLYYHsUmu5ouJLGiifSKOeDNoJjj4XLh7dIN9b
xiqKqy69cK3FCxolkHRyxXtqqzTWMIn/5WgTe1QLyNau7Fqckh49ZLOMxt+/yUFw
7BZy1SbsOFU5Q9D8/RhcQPGX69Wam40dutolucbY38EVAjqr2m7xPi71XAicPNaD
aeQQmxkqtilX4+U9m5/wAl0CAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAOBgNV
HQ8BAf8EBAMCAQYwHQYDVR0OBBYEFMSnsaR7LHH62+FLkHX/xBVghYkQMA0GCSqG
SIb3DQEBBQUAA4IBAQCjGiybFwBcqR7uKGY3Or+Dxz9LwwmglSBd49lZRNI+DT69
ikugdB/OEIKcdBodfpga3csTS7MgROSR6cz8faXbauX+5v3gTt23ADq1cEmv8uXr
AvHRAosZy5Q6XkjEGB5YGV8eAlrwDPGxrancWYaLbumR9YbK+rlmM6pZW87ipxZz
R8srzJmwN0jP41ZL9c8PDHIyh8bwRLtTcm1D9SZImlJnt1ir/md2cXjbDaJWFBM5
JDGFoqgCWjBH4d1QB7wCCZAA62RjYJsWvIjJEubSfZGL+T0yjWW06XyxV3bqxbYo
Ob8VZRzI9neWagqNdwvYkQsEjgfbKbYK7p2CNTUQ
-----END CERTIFICATE-----
)EOF";

const int MAX_AUTH_RETRIES = 3;
const unsigned long AUTH_TOKEN_LIFETIME = 3600000; // 1 hour
const unsigned long SECURITY_CHECK_INTERVAL = 300000; // 5 minutes

Preferences securityPrefs;

bool initSecurity() {
  Serial.println("🔐 Initializing security system...");
  
  // Initialize preferences
  securityPrefs.begin("security", false);
  
  // Load stored security config - enforce production security
  securityConfig.ssl_enabled = true; // Always enable SSL in production
  securityConfig.certificate_validation = true; // Always validate certificates
  securityConfig.device_signature = securityPrefs.getString("device_sig", "");
  securityConfig.api_token = securityPrefs.getString("api_token", "");
  securityConfig.token_expires = securityPrefs.getULong("token_expires", 0);
  
  // Load certificates
  if (!loadCertificates()) {
    Serial.println("⚠️ No certificates found, using basic auth");
  }
  
  // Generate device signature if not exists
  if (securityConfig.device_signature.isEmpty()) {
    securityConfig.device_signature = generateDeviceSignature();
    securityPrefs.putString("device_sig", securityConfig.device_signature);
  }
  
  currentAuthStatus = AUTH_NONE;
  authRetryCount = 0;
  
  Serial.printf("✅ Security initialized. SSL: %s\n", 
                securityConfig.ssl_enabled ? "Enabled" : "Disabled");
  return true;
}

bool authenticateDevice() {
  if (!WiFi.isConnected()) {
    Serial.println("❌ No WiFi connection for authentication");
    return false;
  }
  
  Serial.println("🔑 Authenticating device with server...");
  currentAuthStatus = AUTH_PENDING;
  
  HTTPClient http;
  String url = String("http") + (securityConfig.ssl_enabled ? "s" : "") + 
               "://" + deviceConfig.server_host + 
               ":" + deviceConfig.server_port + 
               "/api/v1/devices/authenticate";
  
  WiFiClientSecure* client = nullptr;
  if (securityConfig.ssl_enabled) {
    client = createSecureClient();
    http.begin(*client, url);
  } else {
    http.begin(url);
  }
  
  http.addHeader("Content-Type", "application/json");
  
  // Create authentication request
  StaticJsonDocument<512> doc;
  doc["device_id"] = deviceConfig.device_id;
  doc["device_type"] = "teddy_bear";
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["mac_address"] = WiFi.macAddress();
  doc["signature"] = securityConfig.device_signature;
  doc["capabilities"] = "audio,motion,leds,websocket";
  
  String payload;
  serializeJson(doc, payload);
  
  int responseCode = http.POST(payload);
  String response = http.getString();
  
  if (client) delete client;
  http.end();
  
  if (responseCode == 200) {
    // Parse authentication response
    StaticJsonDocument<512> responseDoc;
    DeserializationError error = deserializeJson(responseDoc, response);
    
    if (!error) {
      securityConfig.api_token = responseDoc["token"].as<String>();
      securityConfig.token_expires = millis() + (responseDoc["expires_in"].as<unsigned long>() * 1000);
      
      // Store credentials
      securityPrefs.putString("api_token", securityConfig.api_token);
      securityPrefs.putULong("token_expires", securityConfig.token_expires);
      
      currentAuthStatus = AUTH_SUCCESS;
      authRetryCount = 0;
      
      Serial.println("✅ Device authentication successful");
      
      // Show success on LEDs
      setLEDColor("green", 50);
      delay(1000);
      clearLEDs();
      
      return true;
    }
  }
  
  // Authentication failed
  currentAuthStatus = AUTH_FAILED;
  authRetryCount++;
  
  Serial.printf("❌ Authentication failed: %d (attempt %d/%d)\n", 
                responseCode, authRetryCount, MAX_AUTH_RETRIES);
  
  logSecurityEvent("Authentication failed: " + String(responseCode), 3);
  
  // Show error on LEDs
  setLEDColor("red", 70);
  delay(500);
  clearLEDs();
  
  return false;
}

bool renewAuthToken() {
  if (!isAuthenticated()) {
    return authenticateDevice();
  }
  
  Serial.println("🔄 Renewing authentication token...");
  
  HTTPClient http;
  String url = String("http") + (securityConfig.ssl_enabled ? "s" : "") + 
               "://" + deviceConfig.server_host + 
               ":" + deviceConfig.server_port + 
               "/api/v1/devices/renew-token";
  
  WiFiClientSecure* client = nullptr;
  if (securityConfig.ssl_enabled) {
    client = createSecureClient();
    http.begin(*client, url);
  } else {
    http.begin(url);
  }
  
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + securityConfig.api_token);
  
  StaticJsonDocument<256> doc;
  doc["device_id"] = deviceConfig.device_id;
  doc["current_token"] = securityConfig.api_token;
  
  String payload;
  serializeJson(doc, payload);
  
  int responseCode = http.POST(payload);
  String response = http.getString();
  
  if (client) delete client;
  http.end();
  
  if (responseCode == 200) {
    StaticJsonDocument<256> responseDoc;
    if (deserializeJson(responseDoc, response) == DeserializationError::Ok) {
      securityConfig.api_token = responseDoc["token"].as<String>();
      securityConfig.token_expires = millis() + (responseDoc["expires_in"].as<unsigned long>() * 1000);
      
      securityPrefs.putString("api_token", securityConfig.api_token);
      securityPrefs.putULong("token_expires", securityConfig.token_expires);
      
      Serial.println("✅ Token renewed successfully");
      return true;
    }
  }
  
  Serial.printf("❌ Token renewal failed: %d\n", responseCode);
  currentAuthStatus = AUTH_EXPIRED;
  return false;
}

bool isAuthenticated() {
  if (currentAuthStatus != AUTH_SUCCESS) {
    return false;
  }
  
  // Check token expiration
  if (millis() > securityConfig.token_expires) {
    currentAuthStatus = AUTH_EXPIRED;
    return false;
  }
  
  return true;
}

AuthStatus getAuthStatus() {
  return currentAuthStatus;
}

String generateDeviceSignature() {
  String uniqueData = WiFi.macAddress() + String(ESP.getEfuseMac()) + 
                      String(ESP.getChipModel()) + String(FIRMWARE_VERSION);
  
  // Create SHA256 hash
  mbedtls_sha256_context ctx;
  unsigned char hash[32];
  
  mbedtls_sha256_init(&ctx);
  mbedtls_sha256_starts_ret(&ctx, 0);
  mbedtls_sha256_update_ret(&ctx, (const unsigned char*)uniqueData.c_str(), uniqueData.length());
  mbedtls_sha256_finish_ret(&ctx, hash);
  mbedtls_sha256_free(&ctx);
  
  // Convert to hex string
  String signature = "";
  for (int i = 0; i < 32; i++) {
    if (hash[i] < 16) signature += "0";
    signature += String(hash[i], HEX);
  }
  
  return signature;
}

WiFiClientSecure* createSecureClient() {
  WiFiClientSecure* client = new WiFiClientSecure();
  
  // Always validate certificates for production security
  client->setCACert(ROOT_CA_CERT);
  Serial.println("🔐 SSL certificate validation enabled");
  
  // Set client certificate if available
  if (!securityConfig.device_certificate.isEmpty() && !securityConfig.private_key.isEmpty()) {
    client->setCertificate(securityConfig.device_certificate.c_str());
    client->setPrivateKey(securityConfig.private_key.c_str());
  }
  
  return client;
}

bool sendSecureRequest(const String& url, const String& payload, String& response) {
  if (!isAuthenticated()) {
    if (!authenticateDevice()) {
      return false;
    }
  }
  
  HTTPClient http;
  WiFiClientSecure* client = nullptr;
  
  if (securityConfig.ssl_enabled) {
    client = createSecureClient();
    http.begin(*client, url);
  } else {
    http.begin(url);
  }
  
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + securityConfig.api_token);
  http.addHeader("X-Device-ID", deviceConfig.device_id);
  http.addHeader("X-Device-Signature", securityConfig.device_signature);
  
  int responseCode = http.POST(payload);
  response = http.getString();
  
  if (client) delete client;
  http.end();
  
  if (responseCode == 401) {
    // Token expired, try to renew
    if (renewAuthToken()) {
      return sendSecureRequest(url, payload, response);
    }
    return false;
  }
  
  return (responseCode >= 200 && responseCode < 300);
}

bool loadCertificates() {
  securityConfig.device_certificate = securityPrefs.getString("device_cert", "");
  securityConfig.private_key = securityPrefs.getString("private_key", "");
  securityConfig.ca_certificate = securityPrefs.getString("ca_cert", ROOT_CA_CERT);
  
  return (!securityConfig.device_certificate.isEmpty() && 
          !securityConfig.private_key.isEmpty());
}

bool storeCertificates() {
  securityPrefs.putString("device_cert", securityConfig.device_certificate);
  securityPrefs.putString("private_key", securityConfig.private_key);
  securityPrefs.putString("ca_cert", securityConfig.ca_certificate);
  
  return true;
}

void checkSecurityHealth() {
  unsigned long now = millis();
  
  if (now - lastSecurityCheck < SECURITY_CHECK_INTERVAL) {
    return;
  }
  
  lastSecurityCheck = now;
  
  // Check authentication status
  if (!isAuthenticated()) {
    if (authRetryCount < MAX_AUTH_RETRIES) {
      authenticateDevice();
    } else {
      logSecurityEvent("Max authentication retries exceeded", 4);
      handleSecurityError("Authentication completely failed");
    }
  }
  
  // Check for security threats
  if (detectSecurityThreats()) {
    handleSecurityError("Security threat detected");
  }
  
  // Rotate secrets periodically
  if (now % (24 * 60 * 60 * 1000) == 0) { // Daily rotation
    rotateSecrets();
  }
}

bool detectSecurityThreats() {
  // Check for unusual memory patterns
  if (ESP.getFreeHeap() < 5000) {
    logSecurityEvent("Possible memory exhaustion attack", 3);
    return true;
  }
  
  // Check for excessive authentication failures
  if (authRetryCount >= MAX_AUTH_RETRIES) {
    logSecurityEvent("Excessive authentication failures", 4);
    return true;
  }
  
  // Check WiFi signal strength for potential jamming
  if (WiFi.RSSI() < -90) {
    logSecurityEvent("Extremely weak WiFi signal - possible jamming", 2);
  }
  
  return false;
}

void logSecurityEvent(const String& event, int severity) {
  Serial.printf("🔐 SECURITY [%d]: %s\n", severity, event.c_str());
  
  // Log to monitoring system
  logError(ERROR_AUTH_FAILED, event, "security", severity);
  
  // Show security alert on LEDs
  switch (severity) {
    case 1: // Info
      setLEDColor("blue", 30);
      delay(200);
      break;
    case 2: // Warning
      setLEDColor("yellow", 50);
      delay(300);
      break;
    case 3: // Error
      setLEDColor("orange", 70);
      delay(500);
      break;
    case 4: // Critical
      for (int i = 0; i < 5; i++) {
        setLEDColor("red", 100);
        delay(100);
        clearLEDs();
        delay(100);
      }
      break;
  }
  
  clearLEDs();
}

void handleSecurityError(const String& error) {
  Serial.printf("🚨 SECURITY ERROR: %s\n", error.c_str());
  
  // Reset authentication state
  currentAuthStatus = AUTH_FAILED;
  securityConfig.api_token = "";
  securityPrefs.remove("api_token");
  
  // Show critical security error pattern
  for (int i = 0; i < 3; i++) {
    setLEDColor("red", 100);
    delay(300);
    setLEDColor("blue", 100);
    delay(300);
  }
  clearLEDs();
  
  // Log critical error
  logError(ERROR_AUTH_FAILED, "Security system failure: " + error, "", 4);
}

void rotateSecrets() {
  Serial.println("🔄 Rotating security secrets...");
  
  // Generate new device signature
  String newSignature = generateDeviceSignature();
  if (newSignature != securityConfig.device_signature) {
    securityConfig.device_signature = newSignature;
    securityPrefs.putString("device_sig", newSignature);
    Serial.println("✅ Device signature rotated");
  }
  
  // Force token renewal on next request
  securityConfig.token_expires = 0;
  
  logSecurityEvent("Security secrets rotated", 1);
}

bool secureWebSocketConnect() {
  if (!isAuthenticated()) {
    if (!authenticateDevice()) {
      return false;
    }
  }
  
  // Save token to SPIFFS for WebSocket client
  saveAuthTokenToFile(securityConfig.api_token);
  
  // Use authenticated WebSocket connection
  String wsUrl = String("ws") + (securityConfig.ssl_enabled ? "s" : "") + 
                 "://" + deviceConfig.server_host + 
                 ":" + deviceConfig.server_port + 
                 "/ws/device/" + deviceConfig.device_id + 
                 "?token=" + securityConfig.api_token;
  
  Serial.printf("🔐 Connecting to secure WebSocket: %s\n", wsUrl.c_str());
  
  // WebSocket connection will be handled by websocket_handler.cpp
  // This function just provides the secure URL
  
  return true;
}

// دوال إدارة التوكن للWebSocket
bool saveAuthTokenToFile(const String& token) {
  if (!SPIFFS.begin(true)) {
    Serial.println("❌ Failed to mount SPIFFS for token storage");
    return false;
  }
  
  File file = SPIFFS.open("/auth_token.txt", "w");
  if (!file) {
    Serial.println("❌ Failed to create auth token file");
    SPIFFS.end();
    return false;
  }
  
  file.print(token);
  file.close();
  SPIFFS.end();
  
  Serial.println("✅ Auth token saved to SPIFFS");
  return true;
}

String loadAuthTokenFromFile() {
  if (!SPIFFS.begin(true)) {
    return "";
  }
  
  File file = SPIFFS.open("/auth_token.txt", "r");
  if (!file) {
    SPIFFS.end();
    return "";
  }
  
  String token = file.readString();
  token.trim();
  file.close();
  SPIFFS.end();
  
  return token;
}

bool updateWebSocketToken() {
  // تجديد التوكن وحفظه
  if (renewAuthToken()) {
    return saveAuthTokenToFile(securityConfig.api_token);
  }
  return false;
}
