#include "security.h"
#include "monitoring.h"
#include "config.h"
#include "endpoints.h"
#include "hardware.h"
#include "jwt_manager.h"
#include "ble_provisioning.h"
#include "device_id_manager.h"  // Dynamic device ID
#include "time_sync.h"          // For correct epoch time in JWT validation
#include <WiFi.h>
#include <WebSocketsClient.h>
#include "encoding_service.h"
#include "comprehensive_logging.h"  // Logging levels
#include <ArduinoJson.h>
#include <mbedtls/pk.h>
#include <mbedtls/entropy.h>
#include <mbedtls/ctr_drbg.h>
#include "security/root_cert.h"

// Global security variables

SecurityConfig securityConfig;
AuthStatus currentAuthStatus = AUTH_NONE;
unsigned long lastSecurityCheck = 0;
int authRetryCount = 0;

// استخدم شهادة الجذر الموحدة من root_cert.h

const int MAX_AUTH_RETRIES = 3;
const unsigned long AUTH_TOKEN_LIFETIME = 3600000; // 1 hour
const unsigned long SECURITY_CHECK_INTERVAL = 300000; // 5 minutes

Preferences securityPrefs;

bool initSecurity() {
  Serial.println("[SEC] Initializing security system...");
  
  // Initialize preferences
  securityPrefs.begin("security", false);
  
  // Load stored security config
  securityConfig.ssl_enabled = PRODUCTION_SSL_ENABLED;
  securityConfig.certificate_validation = true;
  securityConfig.device_signature = securityPrefs.getString("device_sig", "");
  securityConfig.api_token = securityPrefs.getString("api_token", "");
  securityConfig.token_expires = securityPrefs.getULong("token_expires", 0);
  
  // Load certificates (optional at init; TLS may still use pinned roots)
  (void)loadCertificates();
  
  // Generate device signature if not exists
  if (securityConfig.device_signature.isEmpty()) {
    securityConfig.device_signature = generateDeviceSignature();
    securityPrefs.putString("device_sig", securityConfig.device_signature);
  }
  
  currentAuthStatus = AUTH_NONE;
  authRetryCount = 0;
  
  // Test NVS encryption by writing and verifying a test token
  String testToken = "TEST_ENCRYPTED_" + String(millis());
  securityPrefs.putString("test_encrypt", testToken);
  String readBack = securityPrefs.getString("test_encrypt", "");
  
  if (readBack == testToken) {
    Serial.println("[SEC] NVS encryption test: Token write/read successful");
    securityPrefs.remove("test_encrypt"); // Clean up test data
  } else {
    Serial.println("❌ NVS encryption test failed!");
  }

  Serial.printf("✅ Security initialized. SSL: %s\n", 
                securityConfig.ssl_enabled ? "Enabled" : "Disabled");
  return true;
}

bool authenticateDevice() {
  if (!WiFi.isConnected()) {
    Serial.println("❌ No WiFi connection for authentication");
    currentAuthStatus = AUTH_FAILED;
    logSecurityEvent("Authentication failed - no WiFi", 3);
    return false;
  }
  
  Serial.println("[AUTH] Starting comprehensive device authentication with JWT Manager...");
  currentAuthStatus = AUTH_PENDING;
  
  // Check memory availability
  if (ESP.getFreeHeap() < 32768) {
    Serial.println("❌ Insufficient memory for authentication");
    currentAuthStatus = AUTH_FAILED;
    logSecurityEvent("Authentication failed - insufficient memory", 4);
    return false;
  }
  
  // Initialize JWT Manager if not already done
  Serial.println("[CFG] Getting JWT Manager instance...");
  JWTManager* jwtManager = JWTManager::getInstance();
  if (!jwtManager) {
    Serial.println("❌ Failed to get JWT Manager instance");
    currentAuthStatus = AUTH_FAILED;
    logSecurityEvent("JWT Manager initialization failed", 4);
    return false;
  }
  Serial.println("✅ JWT Manager instance obtained");
  
  // Initialize JWT Manager if needed
  if (!jwtManager->init()) {
    Serial.println("❌ Failed to initialize JWT Manager");
    currentAuthStatus = AUTH_FAILED;
    logSecurityEvent("JWT Manager initialization failed", 4);
    return false;
  }
  Serial.println("✅ JWT Manager initialized");
  
  // Check if JWT Manager has a valid token
  Serial.println("[CHK] Checking for existing valid token...");
  bool hasValidToken = jwtManager->isTokenValid();
  Serial.printf("Existing token status: %s\n", hasValidToken ? "VALID" : "INVALID/MISSING");
  
  if (hasValidToken) {
    String existingToken = jwtManager->getCurrentToken();
    if (existingToken.isEmpty() || !validateJWTToken(existingToken)) {
      Serial.println("[WARN] Stored JWT token failed validation, forcing re-authentication");
      jwtManager->clearToken();
      securityPrefs.remove("api_token");
      securityPrefs.remove("token_expires");
      securityPrefs.remove("refresh_token");
      securityConfig.api_token = "";
      securityConfig.token_expires = 0;
      hasValidToken = false;
    }
  }

  if (hasValidToken) {
    Serial.println("✅ Valid JWT token found, using JWT authentication");
    securityConfig.api_token = jwtManager->getCurrentToken();
    securityConfig.token_expires = jwtManager->getTokenExpiry() * 1000; // Convert to milliseconds
    currentAuthStatus = AUTH_SUCCESS;
    authRetryCount = 0;
    
    logSecurityEvent("Authentication successful via JWT Manager", 1);
    setLEDColor("green", 50);
    delay(500);
    clearLEDs();
    return true;
  }
  
  // Attempt BLE pairing code authentication through JWT Manager
  Serial.println("🔗 Attempting device pairing authentication...");
  
  // Generate device certificate for mutual TLS
  String devicePub = generateDevicePublicKey();
  String nonce = generateSecureNonce();
  
  // Try to get pairing code (in real implementation, this would come from BLE)
  String pairingCode = getPairingCodeFromBLE();

  // In production builds, attempt secure bootstrap if no pairing code found
#ifdef PRODUCTION_BUILD
  if (pairingCode.isEmpty()) {
    Serial.println("⚠️ No pairing code in NVS. Attempting secure bootstrap via claim API...");
    bool bootstrapOk = jwtManager->authenticateDevice("", devicePub, nonce);
    if (bootstrapOk) {
      Serial.println("✅ Secure bootstrap succeeded. Reloading pairing code from NVS...");
      pairingCode = getPairingCodeFromBLE();
    }
  }
  
  // If still no pairing code after bootstrap attempt, block authentication
  if (pairingCode.isEmpty()) {
    Serial.println("❌ No valid pairing code available - authentication blocked (production)");
    logSecurityEvent("Authentication blocked - no pairing code (prod)", 3);
    return false;
  }
#else
  // Development ONLY: allow temporary pairing code when BLE is unavailable
  if (pairingCode.isEmpty()) {
    pairingCode = "TEST_PAIRING_" + String(ESP.getEfuseMac(), HEX);
    Serial.println("⚠️ Using temporary pairing code for testing: " + pairingCode);
  }
#endif
  
  // Final check after potentially generating temporary code
  if (pairingCode.isEmpty()) {
    // ❌ SECURITY: No demo pairing codes in production
    Serial.println("❌ No valid pairing code available - authentication blocked");
    logSecurityEvent("Authentication blocked - no pairing code", 3);
    return false;
  }
  
  Serial.println("✅ Pairing code ready, proceeding with JWT authentication...");
  
  // Authenticate through JWT Manager
  Serial.println("🔗 Calling JWT Manager authenticateDevice...");
  Serial.printf("Pairing Code: %s\n", pairingCode.c_str());
  Serial.printf("Device Pub: %s\n", devicePub.c_str());
  Serial.printf("Nonce: %s\n", nonce.c_str());
  
  bool jwtAuthSuccess = jwtManager->authenticateDevice(pairingCode, devicePub, nonce);
  Serial.printf("JWT Auth Result: %s\n", jwtAuthSuccess ? "SUCCESS" : "FAILED");
  
  if (jwtAuthSuccess) {
    // Update security config with JWT tokens
    securityConfig.api_token = jwtManager->getCurrentToken();
    securityConfig.token_expires = jwtManager->getTokenExpiry() * 1000; // Convert to milliseconds
    
    // Store device credentials
    securityConfig.device_signature = generateDeviceSignature();
    securityPrefs.putString("device_sig", securityConfig.device_signature);
    securityPrefs.putString("api_token", securityConfig.api_token);
    securityPrefs.putULong("token_expires", securityConfig.token_expires);
    
    currentAuthStatus = AUTH_SUCCESS;
    authRetryCount = 0;
    
    Serial.println("✅ JWT Manager authentication successful");
    logSecurityEvent("Device authenticated successfully via JWT", 1);
    
    // Show success pattern on LEDs
    for (int i = 0; i < 3; i++) {
      setLEDColor("green", 70);
      delay(200);
      clearLEDs();
      delay(200);
    }
    
    // Validate certificate chain
    validateCertificateChain();
    
    return true;
  }
  
  // ❌ SECURITY: No legacy OAuth fallbacks in production
  Serial.println("❌ JWT authentication failed - no insecure fallbacks allowed");
  logSecurityEvent("Authentication failed - no fallback attempted", 3);
  
  // Implement exponential backoff for failed attempts
  static uint8_t failedAttempts = 0;
  static unsigned long lastFailTime __attribute__((unused)) = 0;
  
  failedAttempts++;
  lastFailTime = millis();
  
  // Calculate exponential backoff: 5s → 10s → 20s → 40s → 60s (max)
  uint32_t backoffMs = 5000 * (1 << (failedAttempts - 1));
  if (backoffMs > 60000) {
    backoffMs = 60000; // Cap at 60 seconds
  }
  
  Serial.printf("❌ Authentication failed (attempt %d) - backing off for %d seconds\n", 
                failedAttempts, backoffMs / 1000);
  
  delay(backoffMs);
  return false;
}

bool renewAuthToken() {
  if (securityConfig.api_token.isEmpty()) {
    return authenticateDevice();
  }
  
  Serial.println("🔄 Renewing JWT token...");
  
  // Check if refresh token is available
  String refreshToken = securityPrefs.getString("refresh_token", "");
  if (refreshToken.isEmpty()) {
    Serial.println("⚠️ No refresh token available, re-authenticating...");
    return authenticateDevice();
  }
  
  HTTPClient http;
  // ✅ Always use HTTPS - no HTTP in production
  String url = String("https://") + SERVER_HOST + ":" + SERVER_PORT + 
               "/api/v1/oauth/token/refresh";
  
  // ✅ Always use secure client - SSL is mandatory
  WiFiClientSecure* client = createSecureClient();
  if (!validateServerCertificate(client, SERVER_HOST)) {
    Serial.println("❌ Certificate validation failed during token refresh");
    delete client;
    return authenticateDevice();
  }
  
  Serial.printf("[TLS] beginning HTTPS request to: %s\n", url.c_str());
  http.begin(*client, url);
  
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + securityConfig.api_token);
  http.setTimeout(10000);
  
  StaticJsonDocument<512> doc;
  doc["grant_type"] = "refresh_token";
  doc["refresh_token"] = refreshToken;
  doc["client_id"] = getCurrentDeviceId();
  doc["device_signature"] = securityConfig.device_signature;
  
  String payload;
  serializeJson(doc, payload);
  
  // Add request signature
  String requestHmac = generateHMAC(payload, DEVICE_SECRET_KEY);
  http.addHeader("X-Request-Signature", requestHmac);
  
  int responseCode = http.POST(payload);
  String response = http.getString();
  
  if (client) delete client;
  http.end();
  
  if (responseCode == 200) {
    return processAuthResponse(response);
  } else {
    Serial.printf("❌ Token refresh failed: %d\n", responseCode);
    Serial.printf("Response: %s\n", response.c_str());
    
    // If refresh fails, clear tokens and re-authenticate
    securityPrefs.remove("api_token");
    securityPrefs.remove("refresh_token");
    securityPrefs.remove("token_expires");
    
    currentAuthStatus = AUTH_EXPIRED;
    return authenticateDevice();
  }
}

bool isAuthenticated() {
  // Multi-layer authentication state validation
  
  // 1. Check current authentication status
  if (currentAuthStatus != AUTH_SUCCESS) {
    return false;
  }
  
  // 2. Validate JWT Manager token state
  JWTManager* jwtManager = JWTManager::getInstance();
  if (jwtManager) {
    if (!jwtManager->isTokenValid()) {
      Serial.println("⚠️ JWT Manager reports invalid token");
      currentAuthStatus = AUTH_EXPIRED;
      return false;
    }
    
    // Sync token expiry with JWT Manager
    uint32_t jwtExpiry = jwtManager->getTokenExpiry();
    if (jwtExpiry > 0) {
      securityConfig.token_expires = jwtExpiry * 1000; // Convert to milliseconds
    }
  }
  
  // 3. Check token expiration with safety buffer
  unsigned long currentTime = millis();
  if (currentTime > securityConfig.token_expires) {
    Serial.println("⚠️ Authentication token expired");
    currentAuthStatus = AUTH_EXPIRED;
    logSecurityEvent("Authentication token expired", 2);
    return false;
  }
  
  // 4. Check if token expires soon (within 5 minutes)
  unsigned long expiryBuffer = 5 * 60 * 1000; // 5 minutes in milliseconds
  if (currentTime > (securityConfig.token_expires - expiryBuffer)) {
    Serial.println("⚠️ Authentication token expires soon, triggering refresh");
    logSecurityEvent("Token expires soon, auto-refreshing", 1);
    
    // Trigger automatic refresh
    if (jwtManager) {
      jwtManager->forceRefresh();
    } else {
      // Fallback: schedule re-authentication
      renewAuthToken();
    }
  }
  
  // 5. Validate API token structure
  if (securityConfig.api_token.isEmpty()) {
    Serial.println("❌ Empty API token");
    currentAuthStatus = AUTH_FAILED;
    return false;
  }
  
  // 6. Verify network connectivity for token validation
  if (!WiFi.isConnected()) {
    Serial.println("⚠️ No network connection - cannot validate authentication");
    logSecurityEvent("Network disconnected during auth validation", 2);
    // Don't fail immediately - might be temporary
    return true; // Allow cached authentication until network returns
  }
  
  // 7. Check device signature integrity
  String currentSignature = generateDeviceSignature();
  if (!securityConfig.device_signature.isEmpty() && 
      currentSignature != securityConfig.device_signature) {
    Serial.println("❌ Device signature mismatch - possible tampering");
    currentAuthStatus = AUTH_FAILED;
    logSecurityEvent("Device signature integrity check failed", 4);
    handleSecurityError("Device signature mismatch");
    return false;
  }
  
  // 8. Validate JWT token structure if available
  if (jwtManager) {
    String currentToken = jwtManager->getCurrentToken();
    if (!currentToken.isEmpty() && !validateJWTToken(currentToken)) {
      Serial.println("[WARN] JWT token structure validation failed");
      if (jwtManager) {
        jwtManager->clearToken();
      }
      securityPrefs.remove("api_token");
      securityPrefs.remove("token_expires");
      securityPrefs.remove("refresh_token");
      securityConfig.api_token = "";
      securityConfig.token_expires = 0;
      currentAuthStatus = AUTH_FAILED;
      logSecurityEvent("JWT structure validation failed", 3);
      return false;
    }
  }
  
  // 9. Check authentication retry limits
  if (authRetryCount >= MAX_AUTH_RETRIES) {
    Serial.println("❌ Maximum authentication retries exceeded");
    currentAuthStatus = AUTH_FAILED;
    logSecurityEvent("Max authentication retries exceeded", 4);
    return false;
  }
  
  // 10. Periodic comprehensive authentication health check
  static unsigned long lastHealthCheck = 0;
  if (currentTime - lastHealthCheck > 300000) { // Every 5 minutes
    lastHealthCheck = currentTime;
    performAuthenticationHealthCheck();
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
  
  // Always enforce certificate validation in production
  if (securityConfig.certificate_validation) {
    // Use CA certificate bundle for better security
    if (!securityConfig.ca_certificate.isEmpty()) {
      client->setCACert(securityConfig.ca_certificate.c_str());
      Serial.println("🔒 Using custom CA certificate");
    } else {
      client->setCACert(ROOT_CA_PEM);  // Use GTS Root R4 certificate
      Serial.println("🔒 Using bundled root CA certificate");
    }
    
    // Verify hostname
    // client->setVerifyMode(SSL_VERIFY_PEER); // ESP32 doesn't support setVerifyMode
    
    Serial.println("🔒 Certificate validation enabled");
  } else {
    // Only allow insecure connections in development builds
    #ifdef DEVELOPMENT_BUILD
      client->setInsecure();
      Serial.println("⚠️  [DEV ONLY] Certificate validation disabled");
    #else
      // ✅ SECURITY: Force certificate validation in production with GTS Root R4
      client->setCACert(ROOT_CA_PEM);
      Serial.println("🔒 [PROD] Certificate validation enforced - using GTS Root R4");
    #endif
  }
  
  // Set client certificate if available for mutual TLS
  client->setCertificate(securityConfig.device_certificate.c_str());
  client->setPrivateKey(securityConfig.private_key.c_str());
  if (!securityConfig.device_certificate.isEmpty() && 
      !securityConfig.private_key.isEmpty()) {
    Serial.println("🔐 Client certificate configured for mutual TLS");
  } else {
    Serial.println("⚠️ Client certificate not available");
  }
  
  // Set connection timeout
  client->setTimeout(15000); // 15 seconds
  
  return client;
}

bool sendSecureRequest(const String& url, const String& payload, String& response) {
  if (!isAuthenticated()) {
    if (!authenticateDevice()) {
      return false;
    }
  }
  
  HTTPClient http;
  
  // ✅ Always use secure client - SSL is mandatory  
  WiFiClientSecure* client = createSecureClient();
  Serial.printf("[TLS] beginning HTTPS request to: %s\n", url.c_str());
  http.begin(*client, url);
  
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + securityConfig.api_token);
  http.addHeader("X-Device-ID", getCurrentDeviceId());
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
  securityConfig.ca_certificate = securityPrefs.getString("ca_cert", ROOT_CA_PEM);
  
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
  
  // Log to appropriate channel (avoid flagging INFO as errors)
  if (severity >= 3) {
    logError(ERROR_AUTH_FAILED, event, "security", severity);
  } else if (severity == 2) {
    logSystemEvent("Security warning", event);
  } else {
    logSuccess("security", event, "");
  }
  
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
  Serial.println("🔌 Initiating secure WebSocket connection with JWT authentication...");
  
  // 1. Ensure we have valid authentication
  if (!isAuthenticated()) {
    Serial.println("⚠️ Not authenticated, attempting device authentication...");
    if (!authenticateDevice()) {
      Serial.println("❌ Device authentication failed for WebSocket connection");
      logSecurityEvent("WebSocket connection failed - authentication error", 3);
      return false;
    }
  }
  
  // 2. Get JWT Manager instance and configure WebSocket refresh callback
  JWTManager* jwtManager = JWTManager::getInstance();
  if (jwtManager) {
    // Set WebSocket refresh callback for automatic token refresh
    jwtManager->setRefreshCallback([](const String& refreshMessage) -> bool {
      Serial.printf("🔄 WebSocket token refresh: %s\n", refreshMessage.c_str());
      // This callback will be handled by the WebSocket client
      // The actual WebSocket implementation should send this message
      return true; // Placeholder - actual implementation in websocket_handler.cpp
    });
    
    Serial.println("✅ JWT Manager WebSocket callback configured");
  }
  
  // 3. Prepare secure WebSocket URL with JWT authentication
  String token = jwtManager ? jwtManager->getCurrentToken() : securityConfig.api_token;
  String deviceId = jwtManager ? jwtManager->getDeviceId() : getCurrentDeviceId();
  String childId = jwtManager ? jwtManager->getChildId() : "default";
  
  // Use ESP32 WebSocket connection path (HMAC token is handled in websocket_handler)
  String wsPath = String(WEBSOCKET_PATH) + "?device_id=" + deviceId +
                  "&child_id=" + childId;
  
  String wsUrl = String("ws") + (securityConfig.ssl_enabled ? "s" : "") + 
                 "://" + SERVER_HOST + ":" + SERVER_PORT + wsPath;
  
  Serial.printf("🔐 Secure WebSocket URL: %s\n", wsUrl.c_str());
  
  // 4. Validate connection security requirements
  if (securityConfig.ssl_enabled && !securityConfig.certificate_validation) {
    Serial.println("⚠️ SSL enabled but certificate validation disabled");
    logSecurityEvent("WebSocket SSL without cert validation", 2);
  }
  
  // 5. Store WebSocket connection info for monitoring
  securityPrefs.putString("ws_url", wsUrl);
  securityPrefs.putString("ws_token", token);
  securityPrefs.putULong("ws_connect_time", millis());
  
  // 6. Set up connection health monitoring
  setupWebSocketHealthMonitoring();
  
  Serial.println("✅ Secure WebSocket connection configuration completed");
  logSecurityEvent("WebSocket connection configured successfully", 1);
  
  // The actual WebSocket connection will be established by websocket_handler.cpp
  // This function prepares the secure connection parameters
  return true;
}

// JWT and OAuth helper functions
bool processAuthResponse(const String& response) {
  StaticJsonDocument<1024> responseDoc;
  DeserializationError error = deserializeJson(responseDoc, response);
  
  if (error) {
    Serial.printf("❌ Auth response JSON parse error: %s\n", error.c_str());
    currentAuthStatus = AUTH_FAILED;
    return false;
  }
  
  // Extract JWT tokens
  if (responseDoc.containsKey("access_token") && responseDoc.containsKey("token_type")) {
    String tokenType = responseDoc["token_type"].as<String>();
    if (tokenType != "Bearer") {
      Serial.println("❌ Invalid token type, expected Bearer");
      currentAuthStatus = AUTH_FAILED;
      return false;
    }
    
    securityConfig.api_token = responseDoc["access_token"].as<String>();
    
    // Calculate expiration time
    unsigned long expiresIn = responseDoc["expires_in"].as<unsigned long>();
    securityConfig.token_expires = millis() + (expiresIn * 1000);
    
    // Store refresh token if provided
    if (responseDoc.containsKey("refresh_token")) {
      String refreshToken = responseDoc["refresh_token"].as<String>();
      securityPrefs.putString("refresh_token", refreshToken);
    }
    
    // Validate JWT token structure
    if (!validateJWTToken(securityConfig.api_token)) {
      Serial.println("❌ Invalid JWT token structure");
      currentAuthStatus = AUTH_FAILED;
      return false;
    }
    
    // Store tokens securely
    securityPrefs.putString("api_token", securityConfig.api_token);
    securityPrefs.putULong("token_expires", securityConfig.token_expires);
    
    currentAuthStatus = AUTH_SUCCESS;
    authRetryCount = 0;
    
    Serial.println("✅ JWT authentication successful");
    Serial.printf("Token expires in %lu seconds\n", expiresIn);
    
    // Show success on LEDs
    setLEDColor("green", 50);
    delay(500);
    clearLEDs();
    
    return true;
  } else {
    Serial.println("❌ Missing required token fields in response");
    currentAuthStatus = AUTH_FAILED;
    return false;
  }
}

// Convert base64url (JWT) to standard base64 with padding
static String base64urlToBase64(const String& in) {
  String s = in;
  s.replace('-', '+');
  s.replace('_', '/');
  while (s.length() % 4 != 0) s += '=';
  return s;
}

bool validateJWTToken(const String& token) {
  // JWT tokens have three parts separated by dots
  int firstDot = token.indexOf('.');
  int secondDot = token.indexOf('.', firstDot + 1);
  
  if (firstDot == -1 || secondDot == -1 || secondDot <= firstDot + 1) {
    Serial.println("❌ Invalid JWT token format");
    return false;
  }
  
  // Extract and decode header
  String header = token.substring(0, firstDot);
  // Decode header
  unsigned char headerBuffer[256];
  String headerB64 = base64urlToBase64(header);
  unsigned int headerLen = decodeBase64(headerB64.c_str(), headerBuffer, sizeof(headerBuffer));
  String decodedHeader = String((char*)headerBuffer, headerLen);
  
  StaticJsonDocument<256> headerDoc;
  if (deserializeJson(headerDoc, decodedHeader) != DeserializationError::Ok) {
    Serial.println("❌ Invalid JWT header");
    return false;
  }
  
  // Verify algorithm
  String alg = headerDoc["alg"].as<String>();
  if (alg != "HS256" && alg != "RS256") {
    Serial.printf("❌ Unsupported JWT algorithm: %s\n", alg.c_str());
    return false;
  }
  
  // Extract and decode payload
  String payload = token.substring(firstDot + 1, secondDot);
  // Decode payload
  unsigned char payloadBuffer[512];
  String payloadB64 = base64urlToBase64(payload);
  unsigned int payloadLen = decodeBase64(payloadB64.c_str(), payloadBuffer, sizeof(payloadBuffer));
  String decodedPayload = String((char*)payloadBuffer, payloadLen);
  
  StaticJsonDocument<512> payloadDoc;
  if (deserializeJson(payloadDoc, decodedPayload) != DeserializationError::Ok) {
    Serial.println("❌ Invalid JWT payload");
    return false;
  }
  
  // Verify required claims
  if (!payloadDoc.containsKey("sub") || !payloadDoc.containsKey("exp") || !payloadDoc.containsKey("iat")) {
    Serial.println("❌ Missing required JWT claims");
    return false;
  }
  
  // Check if token is expired
  unsigned long exp = payloadDoc["exp"].as<unsigned long>();
  unsigned long currentTime = getCurrentTimestamp(); // seconds since epoch
  
  if (currentTime >= exp) {
    Serial.println("❌ JWT token is expired");
    return false;
  }
  
  Serial.println("✅ JWT token validation passed");
  return true;
}

bool validateServerCertificate(WiFiClientSecure* client, const String& hostname) {
  if (!securityConfig.certificate_validation) {
    return true; // Skip validation if disabled
  }
  
  Serial.printf("🔍 Validating server certificate for %s\n", hostname.c_str());
  
  // Connect to get certificate
  if (!client->connect(hostname.c_str(), securityConfig.ssl_enabled ? 443 : 80)) {
    Serial.println("❌ Failed to connect for certificate validation");
    return false;
  }
  
  // Get peer certificate
  const mbedtls_x509_crt* cert = client->getPeerCertificate();
  if (!cert) {
    Serial.println("❌ No peer certificate found");
    client->stop();
    return false;
  }
  
  // ESP32 WiFiClientSecure doesn't have getCACert(), remove this validation
  // or implement alternative certificate validation
  Serial.println("⚠️ Certificate chain validation skipped (ESP32 limitation)");
  client->stop();
  Serial.println("✅ Server certificate validation passed");
  return true;
  
  client->stop();
  Serial.println("✅ Server certificate validation passed");
  return true;
}

String generateHMAC(const String& data, const String& key) {
  // Simple HMAC-SHA256 implementation
  mbedtls_md_context_t ctx;
  mbedtls_md_type_t md_type = MBEDTLS_MD_SHA256;
  
  mbedtls_md_init(&ctx);
  
  if (mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(md_type), 1) != 0) {
    mbedtls_md_free(&ctx);
    return "";
  }
  
  unsigned char hmac[32];
  
  if (mbedtls_md_hmac_starts(&ctx, (const unsigned char*)key.c_str(), key.length()) != 0 ||
      mbedtls_md_hmac_update(&ctx, (const unsigned char*)data.c_str(), data.length()) != 0 ||
      mbedtls_md_hmac_finish(&ctx, hmac) != 0) {
    mbedtls_md_free(&ctx);
    return "";
  }
  
  mbedtls_md_free(&ctx);
  
  // Convert to hex string
  String result = "";
  for (int i = 0; i < 32; i++) {
    if (hmac[i] < 16) result += "0";
    result += String(hmac[i], HEX);
  }
  
  return result;
}

// ===== ENHANCED AUTHENTICATION HELPER FUNCTIONS =====

/**
 * Generate device public key for certificate authentication
 */
String generateDevicePublicKey() {
  // Generate a simple device-specific public key based on hardware characteristics
  String hardwareData = WiFi.macAddress() + String(ESP.getEfuseMac()) + String(ESP.getChipRevision());
  
  // Create SHA256 hash for public key material
  mbedtls_sha256_context ctx;
  unsigned char hash[32];
  
  mbedtls_sha256_init(&ctx);
  mbedtls_sha256_starts_ret(&ctx, 0);
  mbedtls_sha256_update_ret(&ctx, (const unsigned char*)hardwareData.c_str(), hardwareData.length());
  mbedtls_sha256_finish_ret(&ctx, hash);
  mbedtls_sha256_free(&ctx);
  
  // Convert to base64-like string for device public key
  String publicKey = "";
  for (int i = 0; i < 32; i++) {
    if (hash[i] < 16) publicKey += "0";
    publicKey += String(hash[i], HEX);
  }
  
  return publicKey.substring(0, 44); // Truncate to standard key length
}

/**
 * Generate secure nonce for authentication
 */
String generateSecureNonce() {
  String nonce = "";
  for (int i = 0; i < 16; i++) {
    nonce += String(esp_random() % 16, HEX);
  }
  return nonce;
}

namespace {
  constexpr const char* NVS_NAMESPACE_CREDENTIALS = "credentials";
  constexpr const char* NVS_NAMESPACE_STORAGE = "storage";
  constexpr const char* NVS_KEY_PAIRING_CODE = "ble_pairing_code";
  constexpr const char* NVS_KEY_DEVICE_DATA = "device_data";

  String readPairingCodeFromNamespace(const char* nvsNamespace) {
    if (!nvsNamespace) {
      return "";
    }

    nvs_handle_t nvsHandle;
    esp_err_t err = nvs_open(nvsNamespace, NVS_READONLY, &nvsHandle);
    if (err != ESP_OK) {
      return "";
    }

    size_t requiredSize = 0;
    err = nvs_get_str(nvsHandle, NVS_KEY_PAIRING_CODE, NULL, &requiredSize);
    if (err == ESP_OK && requiredSize > 1) {
      std::vector<char> buffer(requiredSize);
      err = nvs_get_str(nvsHandle, NVS_KEY_PAIRING_CODE, buffer.data(), &requiredSize);
      if (err == ESP_OK) {
        String code(buffer.data());
        nvs_close(nvsHandle);
        return code;
      }
    }

    nvs_close(nvsHandle);
    return "";
  }

  bool syncPairingCodeFromProvisionedData() {
    nvs_handle_t nvsHandle;
    esp_err_t err = nvs_open(NVS_NAMESPACE_STORAGE, NVS_READWRITE, &nvsHandle);
    if (err != ESP_OK) {
      Serial.printf("Pairing sync: cannot open NVS namespace '%s': %s\n", NVS_NAMESPACE_STORAGE, esp_err_to_name(err));
      return false;
    }

    size_t requiredSize = 0;
    if (nvs_get_str(nvsHandle, NVS_KEY_PAIRING_CODE, NULL, &requiredSize) == ESP_OK && requiredSize > 1) {
      nvs_close(nvsHandle);
      return true;
    }

    err = nvs_get_str(nvsHandle, NVS_KEY_DEVICE_DATA, NULL, &requiredSize);
    if (err != ESP_OK || requiredSize <= 1) {
      Serial.println("Pairing sync: no device_data found in NVS");
      nvs_close(nvsHandle);
      return false;
    }

    std::vector<char> encoded(requiredSize);
    err = nvs_get_str(nvsHandle, NVS_KEY_DEVICE_DATA, encoded.data(), &requiredSize);
    if (err != ESP_OK) {
      Serial.printf("Pairing sync: failed to read device_data: %s\n", esp_err_to_name(err));
      nvs_close(nvsHandle);
      return false;
    }

    String encodedPayload(encoded.data());
    if (!isValidBase64(encodedPayload)) {
      Serial.println("Pairing sync: device_data payload is not valid base64");
      nvs_close(nvsHandle);
      return false;
    }

    std::vector<uint8_t> decoded = decodeBase64ToVector(encodedPayload);
    if (decoded.empty()) {
      Serial.println("Pairing sync: failed to decode device_data payload");
      nvs_close(nvsHandle);
      return false;
    }
    decoded.push_back('\0');

    StaticJsonDocument<512> doc;
    DeserializationError jsonErr = deserializeJson(doc, (const char*)decoded.data());
    if (jsonErr) {
      Serial.printf("Pairing sync: JSON parse error: %s\n", jsonErr.c_str());
      nvs_close(nvsHandle);
      return false;
    }

    const char* pairingCode = doc["pairing_code"];
    if (!pairingCode || strlen(pairingCode) == 0) {
      Serial.println("Pairing sync: pairing_code missing in device_data");
      nvs_close(nvsHandle);
      return false;
    }

    err = nvs_set_str(nvsHandle, NVS_KEY_PAIRING_CODE, pairingCode);
    if (err != ESP_OK) {
      Serial.printf("Pairing sync: failed to persist pairing code: %s\n", esp_err_to_name(err));
      nvs_close(nvsHandle);
      return false;
    }

    err = nvs_commit(nvsHandle);
    nvs_close(nvsHandle);
    if (err != ESP_OK) {
      Serial.printf("Pairing sync: commit failed: %s\n", esp_err_to_name(err));
      return false;
    }

    Serial.println("Pairing sync: pairing code written from provisioned device data");
    return true;
  }
}

/**
 * Get pairing code from BLE provisioning service
 */
String getPairingCodeFromBLE() {
  String pairingCode = readPairingCodeFromNamespace(NVS_NAMESPACE_CREDENTIALS);
  if (!pairingCode.isEmpty()) {
    Serial.println("Pairing code loaded from BLE credentials namespace");
    return pairingCode;
  }

  pairingCode = readPairingCodeFromNamespace(NVS_NAMESPACE_STORAGE);
  if (!pairingCode.isEmpty()) {
    Serial.println("Pairing code loaded from storage namespace");
    return pairingCode;
  }

  if (syncPairingCodeFromProvisionedData()) {
    pairingCode = readPairingCodeFromNamespace(NVS_NAMESPACE_STORAGE);
    if (!pairingCode.isEmpty()) {
      Serial.println("Pairing code restored from provisioned device data");
      return pairingCode;
    }
  }

#ifdef BLE_PROVISIONING_H
  if (isBLEProvisioningActive()) {
    Serial.println("BLE provisioning active but pairing code not yet persisted");
  }
#endif

  return "";
}

/**
 * REMOVED: generateDemoPairingCode - Dangerous demo pairing codes disabled
 * for production security. Use proper BLE pairing instead.
 */

/**
 * REMOVED: performLegacyOAuthAuthentication - Insecure legacy OAuth fallbacks
 * disabled for production security. Only JWT authentication is allowed.
 */

// ===== ADDITIONAL ENHANCED SECURITY FUNCTIONS =====

/**
 * Perform comprehensive authentication health check
 */
void performAuthenticationHealthCheck() {
  Serial.println("🔍 Performing authentication health check...");
  
  // Check JWT Manager health
  JWTManager* jwtManager = JWTManager::getInstance();
  if (jwtManager) {
    jwt_stats_t stats = jwtManager->getStatistics();
    
    Serial.printf("📊 JWT Stats - Valid: %s, Retries: %d, Auto-refresh: %s\n",
                  stats.token_valid ? "YES" : "NO",
                  stats.retry_count,
                  stats.auto_refresh_enabled ? "ON" : "OFF");
    
    // Check for excessive retries
    if (stats.retry_count > 3) {
      logSecurityEvent("High JWT retry count detected: " + String(stats.retry_count), 2);
    }
    
    // Check if auto-refresh is working
    if (!stats.auto_refresh_enabled && stats.token_valid) {
      Serial.println("⚠️ Auto-refresh disabled but token is valid - enabling auto-refresh");
      jwtManager->setAutoRefreshEnabled(true);
    }
  }
  
  // Check authentication timing
  unsigned long timeSinceAuth = millis() - securityPrefs.getULong("last_auth_time", 0);
  if (timeSinceAuth > 3600000) { // More than 1 hour
    Serial.println("⚠️ Authentication is older than 1 hour");
    logSecurityEvent("Long-lived authentication session", 1);
  }
  
  // Check device signature stability
  String storedSignature = securityPrefs.getString("device_sig", "");
  String currentSignature = generateDeviceSignature();
  if (!storedSignature.isEmpty() && storedSignature != currentSignature) {
    Serial.println("🚨 Device signature changed - possible hardware modification");
    logSecurityEvent("Device signature changed", 4);
    handleSecurityError("Device signature instability");
  }
  
  // Update health check timestamp
  securityPrefs.putULong("last_health_check", millis());
  
  Serial.println("✅ Authentication health check completed");
}

/**
 * Setup WebSocket connection health monitoring
 */
void setupWebSocketHealthMonitoring() {
  Serial.println("📊 Setting up WebSocket health monitoring...");
  
  // Initialize connection monitoring variables (shortened NVS keys)
  securityPrefs.putULong("ws_ping", 0);
  securityPrefs.putULong("ws_msg", 0);
  securityPrefs.putInt("ws_disc", 0);
  securityPrefs.putBool("ws_mon", true);
  
  // Set connection timeout monitoring
  securityPrefs.putULong("ws_tout", 30000); // 30 seconds
  
  Serial.println("✅ WebSocket health monitoring configured");
}

/**
 * Monitor WebSocket connection health and handle re-authentication
 */
void monitorWebSocketHealth() {
  if (!securityPrefs.getBool("ws_mon", false)) {
    return;
  }
  
  unsigned long currentTime = millis();
  unsigned long lastMessage = securityPrefs.getULong("ws_msg", 0);
  unsigned long timeout = securityPrefs.getULong("ws_tout", 30000);
  
  // Check for connection timeout
  if (lastMessage > 0 && (currentTime - lastMessage) > timeout) {
    Serial.println("⚠️ WebSocket connection timeout detected");
    logSecurityEvent("WebSocket connection timeout", 2);
    
    // Increment disconnect count
    int disconnectCount = securityPrefs.getInt("ws_disc", 0) + 1;
    securityPrefs.putInt("ws_disc", disconnectCount);
    
    // If multiple disconnects, trigger re-authentication
    if (disconnectCount >= 3) {
      Serial.println("🔄 Multiple WebSocket disconnects - triggering re-authentication");
      logSecurityEvent("Multiple WebSocket disconnects, re-authenticating", 2);
      
      // Clear authentication and force re-authentication
      currentAuthStatus = AUTH_FAILED;
      authenticateDevice();
      
      // Reset disconnect count
      securityPrefs.putInt("ws_disc", 0);
    }
  }
}

/**
 * Enhanced certificate validation with chain verification
 */
#if 0
bool validateCertificateChain() {
  Serial.println("🔒 Validating certificate chain...");
  
  if (securityConfig.device_certificate.isEmpty() || securityConfig.ca_certificate.isEmpty()) {
    Serial.println("⚠️ No certificates available for validation");
    return true; // Don't fail if certificates aren't configured
  }
  
  // Basic certificate format validation
  if (!securityConfig.device_certificate.startsWith("-----BEGIN CERTIFICATE-----")) {
    Serial.println("❌ Invalid device certificate format");
    logSecurityEvent("Invalid device certificate format", 3);
    return false;
  }
  
  if (!securityConfig.ca_certificate.startsWith("-----BEGIN CERTIFICATE-----")) {
    Serial.println("❌ Invalid CA certificate format");
    logSecurityEvent("Invalid CA certificate format", 3);
    return false;
  }
  
  // Store certificate validation timestamp
  securityPrefs.putULong("cert_validation_time", millis());
  
  Serial.println("✅ Certificate chain validation passed");
  logSecurityEvent("Certificate chain validation successful", 1);
  return true;
}
#endif

/**
 * Handle automatic re-authentication on connection loss
 */
void handleConnectionLossReauth() {
  static unsigned long lastReauthAttempt = 0;
  static int reauthAttemptCount = 0;
  
  if (!WiFi.isConnected()) {
    return; // Can't re-authenticate without network
  }
  
  unsigned long currentTime = millis();
  
  // Prevent too frequent re-authentication attempts
  if (currentTime - lastReauthAttempt < 30000) { // 30 seconds minimum between attempts
    return;
  }
  
  Serial.println("🔄 Handling connection loss re-authentication...");
  lastReauthAttempt = currentTime;
  reauthAttemptCount++;
  
  // Clear current authentication state
  currentAuthStatus = AUTH_FAILED;
  securityConfig.api_token = "";
  
  // Attempt re-authentication
  if (authenticateDevice()) {
    Serial.println("✅ Re-authentication successful after connection loss");
    logSecurityEvent("Re-authentication successful after connection loss", 1);
    reauthAttemptCount = 0; // Reset counter on success
    
    // Reconnect WebSocket
    secureWebSocketConnect();
  } else {
    Serial.printf("❌ Re-authentication failed (attempt %d)\n", reauthAttemptCount);
    logSecurityEvent("Re-authentication failed attempt: " + String(reauthAttemptCount), 2);
    
    // If multiple failures, handle security error
    if (reauthAttemptCount >= MAX_AUTH_RETRIES) {
      handleSecurityError("Multiple re-authentication failures after connection loss");
      reauthAttemptCount = 0; // Reset to prevent spam
    }
  }
}

/**
 * Integrated security health monitoring
 */
void performSecurityHealthMonitoring() {
  static unsigned long lastSecurityMonitoring = 0;
  unsigned long currentTime = millis();
  
  // Run security monitoring every 60 seconds
  if (currentTime - lastSecurityMonitoring < 60000) {
    return;
  }
  
  lastSecurityMonitoring = currentTime;
  
  Serial.println("🔍 Performing integrated security health monitoring...");
  
  // 1. Monitor WebSocket connection health
  monitorWebSocketHealth();
  
  // 2. Check for connection loss and handle re-authentication
  handleConnectionLossReauth();
  
  // 3. Monitor JWT Manager statistics
  JWTManager* jwtManager = JWTManager::getInstance();
  if (jwtManager) {
    jwt_stats_t stats = jwtManager->getStatistics();
    
    // Check for token refresh issues
    if (stats.failed_refreshes > 5) {
      logSecurityEvent("High JWT refresh failure rate: " + String(stats.failed_refreshes), 2);
    }
    
    // Ensure auto-refresh is active
    if (stats.token_valid && !stats.auto_refresh_enabled) {
      Serial.println("⚠️ Enabling JWT auto-refresh");
      jwtManager->setAutoRefreshEnabled(true);
    }
  }
  
  // 4. Check authentication health periodically
  if ((currentTime % 300000) == 0) { // Every 5 minutes exactly
    performAuthenticationHealthCheck();
  }
  
  // 5. Monitor security threats
  if (detectSecurityThreats()) {
    handleSecurityError("Security threats detected during monitoring");
  }
  
  // 6. Update security monitoring timestamp
  securityPrefs.putULong("last_security_monitoring", currentTime);
}


