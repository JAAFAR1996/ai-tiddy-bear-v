#ifndef TEST_CONFIG_H
#define TEST_CONFIG_H

#include <Arduino.h>

// Testing mode configuration
#ifdef TESTING_MODE
    #define TEST_DEVICE_PREFIX "Teddy-ESP32-TEST"
    #define TEST_CHILD_PREFIX "test-child"
    #define TEST_PARENT_ID "test-parent-001"
    #define USE_DYNAMIC_IDS true
    #define ENABLE_TEST_LOGGING true
    
    // Test-specific OOB secret for predictable HMAC calculation
    #define TEST_OOB_SECRET_PATTERN true
    #define TEST_SERVER_HOST "ai-tiddy-bear-v-xuqy.onrender.com"
    #define TEST_NONCE_LENGTH 16
    
    // Override production settings for testing
    #define TEST_WIFI_TIMEOUT 5000     // Shorter timeout for testing
    #define TEST_HTTP_TIMEOUT 10000    // Shorter HTTP timeout
    #define TEST_MAX_RETRIES 3         // Fewer retries in test
    
#else
    #define USE_DYNAMIC_IDS false
    #define ENABLE_TEST_LOGGING false
    #define TEST_OOB_SECRET_PATTERN false
#endif

// Test utility macros
#ifdef TESTING_MODE
    #define TEST_LOG(msg) if(ENABLE_TEST_LOGGING) Serial.println("[TEST] " + String(msg))
    #define TEST_PRINTF(fmt, ...) if(ENABLE_TEST_LOGGING) Serial.printf("[TEST] " fmt "\n", ##__VA_ARGS__)
#else
    #define TEST_LOG(msg)
    #define TEST_PRINTF(fmt, ...)
#endif

// Test device ID generation
#ifdef TESTING_MODE
inline String generateTestDeviceId() {
    if (USE_DYNAMIC_IDS) {
        return String(TEST_DEVICE_PREFIX) + "-" + String(millis());
    } else {
        return String(TEST_DEVICE_PREFIX) + "-STATIC";
    }
}

inline String generateTestChildId() {
    if (USE_DYNAMIC_IDS) {
        return String(TEST_CHILD_PREFIX) + "-" + String(millis());
    } else {
        return String(TEST_CHILD_PREFIX) + "-001";
    }
}
#endif

#endif // TEST_CONFIG_H