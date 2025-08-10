/*
 * ESP32 AI Teddy Bear - Unified Configuration Header
 * ================================================
 * تعريفات ثابتة موحدة لجميع endpoints والإعدادات
 */

#ifndef ESP32_CONFIG_HEADERS_H
#define ESP32_CONFIG_HEADERS_H

// ==============================================
// UNIFIED HOST CONFIGURATION
// ==============================================
// الهوست الموحد - لا تغير هذا أبداً!
#define DEFAULT_SERVER_HOST "ai-tiddy-bear-v.onrender.com"
#define DEFAULT_SERVER_PORT 443

// ==============================================
// API ENDPOINTS - تطابق السيرفر تماماً
// ==============================================
#define FIRMWARE_UPDATE_ENDPOINT   "/api/esp32/firmware"
#define CONFIG_UPDATE_ENDPOINT     "/api/esp32/config"
#define WS_CONNECT_ENDPOINT        "/ws/esp32/connect"

// Full URLs - للاستخدام المباشر
#define DEFAULT_FIRMWARE_UPDATE_URL "https://ai-tiddy-bear-v.onrender.com/api/esp32/firmware"
#define DEFAULT_CONFIG_UPDATE_URL   "https://ai-tiddy-bear-v.onrender.com/api/esp32/config"
#define DEFAULT_WS_CONNECT_URL      "wss://ai-tiddy-bear-v.onrender.com/ws/esp32/connect"

// ==============================================
// SSL/TLS CONFIGURATION
// ==============================================
#define USE_SSL_BUNDLE true              // استخدم Mozilla CA bundle
#define VERIFY_SSL_CERTIFICATES true     // لا تعطل التحقق
#define TLS_TIMEOUT_MS 10000             // 10 seconds timeout

// ==============================================
// NTP CONFIGURATION
// ==============================================
#define NTP_SERVER_PRIMARY   "pool.ntp.org"
#define NTP_SERVER_SECONDARY "time.nist.gov"
#define NTP_TIMEOUT_MS 5000              // 5 seconds timeout
#define REQUIRED_TIME_ACCURACY 60        // seconds tolerance

// ==============================================
// DEVICE CONFIGURATION
// ==============================================
#define DEVICE_ID_LENGTH 16
#define MAX_CHILD_NAME_LENGTH 30
#define MIN_CHILD_AGE 3
#define MAX_CHILD_AGE 13

// ==============================================
// NETWORK CONFIGURATION
// ==============================================
#define WIFI_CONNECT_TIMEOUT_MS 15000    // 15 seconds
#define HTTP_TIMEOUT_MS 10000            // 10 seconds
#define WS_RECONNECT_INTERVAL_MS 5000    // 5 seconds
#define MAX_RETRY_ATTEMPTS 3

// ==============================================
// FIRMWARE UPDATE CONFIGURATION
// ==============================================
#define FIRMWARE_VERSION "1.2.0"
#define UPDATE_CHECK_INTERVAL_MS 3600000 // 1 hour
#define FORCE_UPDATE_THRESHOLD 7         // days

// ==============================================
// DEBUG AND LOGGING
// ==============================================
#ifdef DEBUG
    #define DEBUG_PRINT(x) Serial.print(x)
    #define DEBUG_PRINTLN(x) Serial.println(x)
    #define DEBUG_PRINTF(fmt, ...) Serial.printf(fmt, ##__VA_ARGS__)
#else
    #define DEBUG_PRINT(x)
    #define DEBUG_PRINTLN(x)  
    #define DEBUG_PRINTF(fmt, ...)
#endif

// ==============================================
// VALIDATION MACROS
// ==============================================
#define VALIDATE_HOST(host) \
    (strstr(host, "ai-tiddy-bear-v.onrender.com") != nullptr)

#define VALIDATE_ENDPOINT(endpoint) \
    (strlen(endpoint) > 0 && endpoint[0] == '/')

// ==============================================
// ERROR CODES
// ==============================================
typedef enum {
    ESP32_SUCCESS = 0,
    ESP32_ERROR_WIFI_FAILED = -1,
    ESP32_ERROR_NTP_FAILED = -2,
    ESP32_ERROR_SSL_FAILED = -3,
    ESP32_ERROR_HTTP_FAILED = -4,
    ESP32_ERROR_JSON_PARSE_FAILED = -5,
    ESP32_ERROR_CONFIG_INVALID = -6,
    ESP32_ERROR_TIME_SYNC_FAILED = -7
} esp32_error_t;

#endif // ESP32_CONFIG_HEADERS_H