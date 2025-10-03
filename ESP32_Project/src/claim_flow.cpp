/*
 * ESP32 Device Claim Flow Implementation
 * ======================================
 * HMAC-SHA256 authentication for device claiming
 */

#include <Arduino.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <mbedtls/sha256.h>
#include <mbedtls/md.h>
#include <WiFi.h>
#include "config.h"
#include "test_config.h"
#include "endpoints.h"
#include "security.h"
#include "jwt_manager.h"
#include "device_id_manager.h"

// Logging
static const char* TAG = "ClaimFlow";

// Device claiming state
static bool deviceClaimed = false;
static String deviceToken = "";
static String childId = "";

/**
 * Normalize device ID to match server regex ^[a-zA-Z0-9_-]+$
 * Removes colons, dots, and other invalid characters from MAC address
 */
static String canonicalDeviceId() {
  String id = WiFi.macAddress();   // Example: "CC:DB:A7:95:BA:A4"
  id.replace(":", "");             // Remove colons
  id.replace("-", "");             // Remove dashes
  id.replace(".", "");             // Remove dots
  id.toUpperCase();                // "CCDBA795BAA4" - matches ^[A-Za-z0-9_-]+$
  return id;
}

/**
 * Generate OOB (Out-of-Band) secret for device
 * Algorithm matches server implementation
 */
String generateOOBSecret(const String& deviceId) {
#ifdef TESTING_MODE
  // للاختبار: سر ثابت قابل للتنبؤ لسهولة التحقق
  if (TEST_OOB_SECRET_PATTERN) {
    TEST_LOG("Using test OOB secret pattern for device: " + deviceId);
    // Generate predictable but unique secret for testing
    String testSecret = "TEST_SECRET_" + deviceId.substring(deviceId.length()-8);
    // Pad to 64 chars (32 bytes hex)
    while (testSecret.length() < 64) {
      testSecret += "0";
    }
    return testSecret.substring(0, 64).toUpperCase();
  }
#endif

  // للإنتاج: نفس الآلية الحالية  
  const char* salt = "ai-teddy-bear-oob-secret-v1";
  
  // First SHA256: device_id:salt
  String hashInput = deviceId + ":" + salt;
  
  uint8_t firstHash[32];
  mbedtls_sha256_context sha256_ctx;
  mbedtls_sha256_init(&sha256_ctx);
  mbedtls_sha256_starts(&sha256_ctx, 0);
  mbedtls_sha256_update(&sha256_ctx, (const unsigned char*)hashInput.c_str(), hashInput.length());
  mbedtls_sha256_finish(&sha256_ctx, firstHash);
  mbedtls_sha256_free(&sha256_ctx);
  
  // Convert to hex string
  char hexHash[65];
  for(int i = 0; i < 32; i++) {
    sprintf(&hexHash[i*2], "%02x", firstHash[i]);
  }
  hexHash[64] = '\0';
  
  // Second SHA256: hexHash + salt
  String secondInput = String(hexHash) + salt;
  
  uint8_t finalHash[32];
  mbedtls_sha256_init(&sha256_ctx);
  mbedtls_sha256_starts(&sha256_ctx, 0);
  mbedtls_sha256_update(&sha256_ctx, (const unsigned char*)secondInput.c_str(), secondInput.length());
  mbedtls_sha256_finish(&sha256_ctx, finalHash);
  mbedtls_sha256_free(&sha256_ctx);
  
  // Convert to uppercase hex string
  char finalHex[65];
  for(int i = 0; i < 32; i++) {
    sprintf(&finalHex[i*2], "%02X", finalHash[i]);
  }
  finalHex[64] = '\0';
  
  return String(finalHex);
}

/**
 * Generate random nonce (16 bytes as hex string)
 * Uses esp_random() for cryptographically secure randomness
 */
String generateNonce() {
  uint8_t nonce[16];
  for(int i = 0; i < 16; i++) {
    nonce[i] = esp_random() & 0xFF;
  }
  
  char hexNonce[33];
  for(int i = 0; i < 16; i++) {
    sprintf(&hexNonce[i*2], "%02x", nonce[i]);
  }
  hexNonce[32] = '\0';
  
  return String(hexNonce);
}

/**
 * Calculate HMAC-SHA256 for authentication
 */
String calculateHMAC(const String& deviceId, const String& childId, 
                     const String& nonce, const String& oobSecret) {
  
  // Convert OOB secret from hex to bytes
  uint8_t key[32];
  for(int i = 0; i < 32; i++) {
    char hex[3] = {oobSecret[i*2], oobSecret[i*2+1], '\0'};
    key[i] = strtol(hex, NULL, 16);
  }
  
  // Convert nonce from hex to bytes
  uint8_t nonceBytes[16];
  for(int i = 0; i < 16; i++) {
    char hex[3] = {nonce[i*2], nonce[i*2+1], '\0'};
    nonceBytes[i] = strtol(hex, NULL, 16);
  }
  
  // Prepare HMAC context
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  
  const mbedtls_md_info_t* md_info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_setup(&ctx, md_info, 1); // 1 for HMAC
  
  // Start HMAC
  mbedtls_md_hmac_starts(&ctx, key, 32);
  
  // Update with device_id + child_id + nonce
  mbedtls_md_hmac_update(&ctx, (const unsigned char*)deviceId.c_str(), deviceId.length());
  mbedtls_md_hmac_update(&ctx, (const unsigned char*)childId.c_str(), childId.length());
  mbedtls_md_hmac_update(&ctx, nonceBytes, 16);
  
  // Finish HMAC
  uint8_t hmacResult[32];
  mbedtls_md_hmac_finish(&ctx, hmacResult);
  mbedtls_md_free(&ctx);
  
  // Convert to hex string
  char hexHmac[65];
  for(int i = 0; i < 32; i++) {
    sprintf(&hexHmac[i*2], "%02x", hmacResult[i]);
  }
  hexHmac[64] = '\0';
  
  return String(hexHmac);
}

/**
 * Log authentication attempt details
 */
void logAuthenticationAttempt(const String& deviceId, const String& childId, 
                              const String& nonce, const String& result, 
                              int httpCode = 0, const String& serverResponse = "") {
#ifdef TESTING_MODE
  if (ENABLE_TEST_LOGGING) {
    Serial.println("🔐 AUTH_DEBUG:");
    Serial.println("  Device: " + deviceId);
    Serial.println("  Child: " + childId);
    Serial.println("  Nonce: " + nonce);
    Serial.println("  Result: " + result);
    if (httpCode > 0) {
      Serial.println("  HTTP Code: " + String(httpCode));
    }
    if (serverResponse.length() > 0) {
      Serial.println("  Server Response: " + serverResponse.substring(0, 100) + "...");
    }
    Serial.println("  Timestamp: " + String(millis()));
    Serial.println("  Free Heap: " + String(ESP.getFreeHeap()));
  }
#else
  // In production, log only essential info
  Serial.printf("[%s] Auth attempt: Device=%s, Child=%s, Result=%s, HTTP=%d\n", 
                TAG, deviceId.c_str(), childId.c_str(), result.c_str(), httpCode);
#endif
}

/**
 * Claim device with server
 */
bool claimDevice(const String& deviceId, const String& targetChildId) {
  Serial.printf("[%s] Starting device claim process...\n", TAG);
  
  // Use canonical device ID to match server regex ^[a-zA-Z0-9_-]+$
  String canonicalId = canonicalDeviceId();
  Serial.printf("[%s] Canonical Device ID: %s (from MAC: %s)\n", TAG, canonicalId.c_str(), WiFi.macAddress().c_str());
  
  // Generate OOB secret using canonical ID
  String oobSecret = generateOOBSecret(canonicalId);
#ifdef DEVELOPMENT_BUILD
  Serial.printf("[%s] OOB Secret generated: %s...\n", TAG, oobSecret.substring(0, 16).c_str());
#else
  Serial.printf("[%s] OOB Secret generated (length: %d)\n", TAG, oobSecret.length());
#endif
  
  // Generate nonce
  String nonce = generateNonce();
#ifdef DEVELOPMENT_BUILD
  Serial.printf("[%s] Nonce generated: %s\n", TAG, nonce.c_str());
#else
  Serial.printf("[%s] Nonce generated (length: %d)\n", TAG, nonce.length());
#endif
  
  // Calculate HMAC using canonical device ID
  String hmac = calculateHMAC(canonicalId, targetChildId, nonce, oobSecret);
#ifdef DEVELOPMENT_BUILD
  Serial.printf("[%s] HMAC calculated: %s...\n", TAG, hmac.substring(0, 16).c_str());
#else
  Serial.printf("[%s] HMAC calculated (length: %d)\n", TAG, hmac.length());
#endif
  
  // Prepare JSON payload with canonical device ID
  StaticJsonDocument<512> doc;
  doc["device_id"] = canonicalId;  // Use canonical ID in payload
  doc["child_id"] = targetChildId;
  doc["nonce"] = nonce;
  doc["hmac_hex"] = hmac;
  doc["firmware_version"] = FIRMWARE_VERSION;
  
  String jsonPayload;
  serializeJson(doc, jsonPayload);
  
  // Send HTTP request
  HTTPClient http;
  String url = String(API_BASE_URL) + "/api/v1/pair/claim";
  
  Serial.printf("[%s] Sending claim request to: %s\n", TAG, url.c_str());
  
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("User-Agent", "ESP32-TeddyBear/" + String(FIRMWARE_VERSION));
  
  int httpCode = http.POST(jsonPayload);
  String response = http.getString();
  
  // Log authentication attempt with canonical ID
  logAuthenticationAttempt(canonicalId, targetChildId, nonce, 
                          httpCode == HTTP_CODE_OK ? "SUCCESS" : "FAILED", 
                          httpCode, response);
  
  if (httpCode == HTTP_CODE_OK) {
    StaticJsonDocument<1024> responseDoc;
    DeserializationError error = deserializeJson(responseDoc, response);
    
    if (!error) {
      // Extract token and save
      if (responseDoc.containsKey("access_token")) {
        deviceToken = responseDoc["access_token"].as<String>();
        childId = targetChildId;
        deviceClaimed = true;
        
        // Store in JWT Manager if available
        JWTManager* jwtManager = JWTManager::getInstance();
        if (jwtManager) {
          // Store token with default TTL
          jwtManager->storeToken(deviceToken, JWT_TOKEN_TTL_SEC);
          // Note: deviceId and childId are stored internally by JWT manager during authentication
        }
        
        Serial.printf("[%s] ✅ Device claimed successfully!\n", TAG);
#ifdef DEVELOPMENT_BUILD
        Serial.printf("[%s] Token: %s...\n", TAG, deviceToken.substring(0, 20).c_str());
#else
        Serial.printf("[%s] Token received (length: %d)\n", TAG, deviceToken.length());
#endif
        
        http.end();
        return true;
      } else {
        Serial.printf("[%s] ❌ No access token in response\n", TAG);
      }
    } else {
      Serial.printf("[%s] ❌ JSON parse error: %s\n", TAG, error.c_str());
    }
  } else {
    Serial.printf("[%s] ❌ HTTP error: %d\n", TAG, httpCode);
    
    // Don't retry on client errors (4xx) - these are permanent failures
    if (httpCode >= 400 && httpCode < 500) {
      Serial.printf("[%s] Client error %d - not retrying\n", TAG, httpCode);
      if (httpCode == 422) {
        Serial.printf("[%s] Validation error - check device_id format and HMAC calculation\n", TAG);
      }
      http.end();
      return false;
    }
    
    if (httpCode > 0) {
      String errorResponse = http.getString();
      Serial.printf("[%s] Error response: %s\n", TAG, errorResponse.c_str());
    }
  }
  
  http.end();
  return false;
}

/**
 * Check if device is claimed
 */
bool isDeviceClaimed() {
  return deviceClaimed;
}

/**
 * Get device token
 */
String getDeviceToken() {
  return deviceToken;
}

/**
 * Get child ID
 */
String getChildId() {
  return childId;
}

/**
 * Clear claim data (for reset)
 */
void clearClaimData() {
  deviceClaimed = false;
  deviceToken = "";
  childId = "";
  
  // Clear JWT Manager
  JWTManager* jwtManager = JWTManager::getInstance();
  if (jwtManager) {
    jwtManager->clearToken();
  }
  
  Serial.printf("[%s] Claim data cleared\n", TAG);
}

/**
 * Test claim flow (for development)
 */
void testClaimFlow() {
  #ifdef DEVELOPMENT_BUILD
  Serial.println("===== CLAIM FLOW TEST =====");
  
  String testDeviceId = getCurrentDeviceId();
#ifdef TESTING_MODE
  String testChildId = generateTestChildId();
#else
  String testChildId = "child-unknown";
#endif
  
  Serial.printf("Device ID: %s\n", testDeviceId.c_str());
  Serial.printf("Child ID: %s\n", testChildId.c_str());
  
  // Test OOB generation
  String oob = generateOOBSecret(testDeviceId);
  Serial.printf("OOB Secret: %s\n", oob.c_str());
  
  // Test nonce generation
  String nonce = generateNonce();
  Serial.printf("Nonce: %s\n", nonce.c_str());
  
  // Test HMAC calculation
  String hmac = calculateHMAC(testDeviceId, testChildId, nonce, oob);
  Serial.printf("HMAC: %s\n", hmac.c_str());
  
  Serial.println("===========================");
  #endif
}