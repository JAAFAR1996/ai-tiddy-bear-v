/*
 * JWT Manager Header for AI Teddy Bear ESP32-S3
 * Enterprise-grade JWT token management with auto-refresh
 * 
 * Features:
 * - Thread-safe operations with mutexes
 * - Secure NVS storage for tokens
 * - Auto-refresh 60 seconds before expiry
 * - REST API integration (/device/session)
 * - WebSocket auth refresh support
 * - Exponential backoff retry logic
 * - Production-ready error handling
 * - Memory leak protection
 * 
 * Author: Expert ESP32 Engineer (1000 years experience)
 * Version: 2.0.0 Enterprise Edition
 */

#ifndef JWT_MANAGER_H
#define JWT_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_timer.h"
#include "nvs.h"

#ifdef __cplusplus
extern "C" {
#endif

// Constants
#define JWT_TOKEN_TTL_SEC           300     // 5 minutes
#define JWT_REFRESH_BUFFER_SEC      60      // Refresh 60 seconds before expiry
#define JWT_MAX_RETRY_COUNT         5       // Maximum retry attempts
#define JWT_HTTP_TIMEOUT_MS         10000   // HTTP request timeout
#define JWT_OPERATION_TIMEOUT_MS    5000    // Mutex timeout
#define JWT_NVS_NAMESPACE           "jwt_mgr"
#define JWT_TOKEN_KEY               "token"
#define JWT_EXPIRY_KEY              "expiry"
#define JWT_DEVICE_ID_KEY           "device_id"
#define JWT_CHILD_ID_KEY            "child_id"

// NVS Storage Keys
#define JWT_NVS_RETRY_COUNT_KEY     "retry_count"
#define JWT_NVS_LAST_REFRESH_KEY    "last_refresh"
#define JWT_NVS_CONFIG_KEY          "config"

// Error Codes
typedef enum {
    JWT_ERROR_NONE = 0,
    JWT_ERROR_NOT_INITIALIZED,
    JWT_ERROR_INVALID_PARAMS,
    JWT_ERROR_HTTP_FAILED,
    JWT_ERROR_PARSE_FAILED,
    JWT_ERROR_TOKEN_EXPIRED,
    JWT_ERROR_STORAGE_FAILED,
    JWT_ERROR_MUTEX_TIMEOUT,
    JWT_ERROR_REFRESH_IN_PROGRESS,
    JWT_ERROR_MAX_RETRIES_REACHED,
    JWT_ERROR_CALLBACK_NOT_SET
} jwt_error_t;

// JWT Statistics Structure
typedef struct {
    bool token_valid;
    uint32_t token_expiry;
    uint8_t retry_count;
    uint32_t last_refresh_attempt;
    bool auto_refresh_enabled;
    bool refresh_in_progress;
    uint32_t total_refreshes;
    uint32_t failed_refreshes;
    uint32_t last_error_code;
    char device_id[64];
    char child_id[64];
} jwt_stats_t;

// Callback function type for WebSocket refresh
typedef bool (*jwt_refresh_callback_t)(const String& refreshMessage);

// Event callback for JWT events
typedef enum {
    JWT_EVENT_TOKEN_REFRESHED,
    JWT_EVENT_TOKEN_EXPIRED,
    JWT_EVENT_REFRESH_FAILED,
    JWT_EVENT_AUTHENTICATION_SUCCESS,
    JWT_EVENT_AUTHENTICATION_FAILED
} jwt_event_type_t;

typedef struct {
    jwt_event_type_t type;
    uint32_t timestamp;
    jwt_error_t error_code;
    char message[128];
} jwt_event_t;

typedef void (*jwt_event_callback_t)(const jwt_event_t* event);

#ifdef __cplusplus
}
#endif

/*
 * JWT Manager Class - Enterprise Edition
 * Thread-safe singleton for JWT token management
 */
class JWTManager {
public:
    // Singleton pattern
    static JWTManager* getInstance();
    
    // Core functionality
    bool init();
    bool authenticateDevice(const String& pairingCode, const String& devicePub = "", const String& nonce = "");
    bool refreshToken();
    bool handleRefreshResponse(const String& response);
    bool isTokenValid();
    void clearToken();
    
    // Token management
    String getCurrentToken();
    String getDeviceId();
    String getChildId();
    uint32_t getTokenExpiry();
    int32_t getTimeUntilExpiry();
    bool storeToken(const String& token, uint32_t expiresInSec);
    
    // Auto-refresh management
    void scheduleAutoRefresh();
    void setAutoRefreshEnabled(bool enabled);
    bool isAutoRefreshEnabled();
    void setRefreshCallback(jwt_refresh_callback_t callback);
    
    // Retry management
    uint8_t getRetryCount();
    void resetRetryCount();
    
    // Statistics and monitoring
    jwt_stats_t getStatistics();
    
    // Manual operations
    bool forceRefresh();
    
    // Event handling
    void setEventCallback(jwt_event_callback_t callback);
    
    // Configuration
    void setHttpTimeout(uint32_t timeoutMs);
    void setMaxRetryCount(uint8_t maxRetries);
    void setRefreshBuffer(uint32_t bufferSec);
    
    // Destructor
    ~JWTManager();

private:
    // Singleton constructor
    JWTManager();
    JWTManager(const JWTManager&) = delete;
    JWTManager& operator=(const JWTManager&) = delete;
    
    // Static members
    static JWTManager* instance;
    static SemaphoreHandle_t mutex;
    static TaskHandle_t refreshTaskHandle;
    static esp_timer_handle_t autoRefreshTimer;
    
    // Member variables
    bool initialized;
    String currentToken;
    String deviceId;
    String childId;
    uint32_t tokenExpiry;
    bool autoRefreshEnabled;
    bool refreshInProgress;
    uint8_t retryCount;
    uint32_t lastRefreshAttempt;
    uint32_t totalRefreshes;
    uint32_t failedRefreshes;
    uint32_t httpTimeoutMs;
    uint8_t maxRetryCount;
    uint32_t refreshBufferSec;
    
    // Callbacks
    jwt_refresh_callback_t refreshCallback;
    jwt_event_callback_t eventCallback;
    
    // Storage
    nvs_handle_t nvsHandle;
    
    // HTTP client
    HTTPClient* httpClient;
    
    // Private methods
    bool performDeviceAuthentication(const String& pairingCode, const String& devicePub, const String& nonce);
    bool parseAuthenticationResponse(const String& response);
    void loadTokenFromNVS();
    void saveConfigToNVS();
    void loadConfigFromNVS();
    String generateNonce();
    String getDeviceUniqueId();
    String getDeviceOOBSecret();
    String calculateDeviceHMAC(const String& device_id, const String& child_id, const String& nonce_hex, const String& oob_secret_hex);
    uint32_t calculateExponentialBackoff(uint8_t attempt);
    uint32_t getCurrentTimestamp();
    void persistPairingArtifacts(const String& pairingCode, const String& provisioningPayload);
    void cleanup();
    void notifyEvent(jwt_event_type_t type, jwt_error_t errorCode = JWT_ERROR_NONE, const char* message = nullptr);
    
    // Static callbacks
    static void autoRefreshTimerCallback(void* arg);
    static void refreshTokenTask(void* parameter);
};

/*
 * Utility Functions
 */

/**
 * Validate JWT token format (basic validation)
 * @param token JWT token string
 * @return true if format is valid, false otherwise
 */
bool jwt_validate_format(const String& token);

/**
 * Extract payload from JWT token (without signature verification)
 * @param token JWT token string
 * @param payload Output buffer for payload JSON
 * @return true if extraction successful, false otherwise
 */
bool jwt_extract_payload(const String& token, String& payload);

/**
 * Get expiry timestamp from JWT payload
 * @param payload JWT payload JSON string
 * @return expiry timestamp or 0 if invalid
 */
uint32_t jwt_get_expiry_from_payload(const String& payload);

/**
 * Check if JWT token is expired
 * @param token JWT token string
 * @param bufferSec Buffer time in seconds to consider as expired early
 * @return true if expired (or will expire within buffer time)
 */
bool jwt_is_expired(const String& token, uint32_t bufferSec = 30);

/*
 * Configuration Macros
 */

// Enable/disable features at compile time
#ifndef JWT_ENABLE_DEBUG_LOGGING
#define JWT_ENABLE_DEBUG_LOGGING 1
#endif

#ifndef JWT_ENABLE_STATISTICS
#define JWT_ENABLE_STATISTICS 1
#endif

#ifndef JWT_ENABLE_EVENT_CALLBACKS
#define JWT_ENABLE_EVENT_CALLBACKS 1
#endif

// Memory settings
#ifndef JWT_MAX_TOKEN_LENGTH
#define JWT_MAX_TOKEN_LENGTH 1024
#endif

#ifndef JWT_MAX_RESPONSE_SIZE
#define JWT_MAX_RESPONSE_SIZE 2048
#endif

// Timing settings
#ifndef JWT_DEFAULT_HTTP_TIMEOUT_MS
#define JWT_DEFAULT_HTTP_TIMEOUT_MS 10000
#endif

#ifndef JWT_DEFAULT_REFRESH_BUFFER_SEC
#define JWT_DEFAULT_REFRESH_BUFFER_SEC 60
#endif

#ifndef JWT_DEFAULT_MAX_RETRY_COUNT
#define JWT_DEFAULT_MAX_RETRY_COUNT 5
#endif

/*
 * Debug Macros
 */
#if JWT_ENABLE_DEBUG_LOGGING
    #define JWT_LOGI(tag, format, ...) ESP_LOGI(tag, format, ##__VA_ARGS__)
    #define JWT_LOGW(tag, format, ...) ESP_LOGW(tag, format, ##__VA_ARGS__)
    #define JWT_LOGE(tag, format, ...) ESP_LOGE(tag, format, ##__VA_ARGS__)
    #define JWT_LOGD(tag, format, ...) ESP_LOGD(tag, format, ##__VA_ARGS__)
#else
    #define JWT_LOGI(tag, format, ...)
    #define JWT_LOGW(tag, format, ...)
    #define JWT_LOGE(tag, format, ...) ESP_LOGE(tag, format, ##__VA_ARGS__)
    #define JWT_LOGD(tag, format, ...)
#endif

/*
 * Error Handling Macros
 */
#define JWT_CHECK_INIT(mgr) \
    do { \
        if (!(mgr)->initialized) { \
            ESP_LOGE("JWT_MGR", "JWT Manager not initialized"); \
            return false; \
        } \
    } while(0)

#define JWT_CHECK_PARAM(param) \
    do { \
        if (!(param)) { \
            ESP_LOGE("JWT_MGR", "Invalid parameter: " #param); \
            return false; \
        } \
    } while(0)

#define JWT_MUTEX_TAKE(mutex, timeout) \
    do { \
        if (xSemaphoreTake(mutex, pdMS_TO_TICKS(timeout)) != pdTRUE) { \
            ESP_LOGE("JWT_MGR", "Failed to acquire mutex"); \
            return false; \
        } \
    } while(0)

#define JWT_MUTEX_GIVE(mutex) \
    do { \
        xSemaphoreGive(mutex); \
    } while(0)

/*
 * Version Information
 */
#define JWT_MANAGER_VERSION_MAJOR    2
#define JWT_MANAGER_VERSION_MINOR    0
#define JWT_MANAGER_VERSION_PATCH    0
#define JWT_MANAGER_VERSION_STRING   "2.0.0"
#define JWT_MANAGER_BUILD_DATE       __DATE__ " " __TIME__

/*
 * API Response Structures
 */
typedef struct {
    int http_code;
    String response_body;
    bool success;
    jwt_error_t error_code;
    uint32_t response_time_ms;
} jwt_api_response_t;

typedef struct {
    String device_id;
    String child_id;
    String device_session_jwt;
    uint32_t expires_in_sec;
} jwt_auth_response_t;

typedef struct {
    String type;
    uint32_t exp_in_sec;
    String reason; // For error responses
} jwt_refresh_response_t;

/*
 * Advanced Configuration Structure
 */
typedef struct {
    uint32_t http_timeout_ms;
    uint8_t max_retry_count;
    uint32_t refresh_buffer_sec;
    bool auto_refresh_enabled;
    bool enable_statistics;
    bool enable_event_callbacks;
    bool enable_debug_logging;
    String server_host;
    uint16_t server_port;
    bool ssl_enabled;
    String ca_cert; // For SSL verification
} jwt_config_t;

/*
 * Thread-safe Helper Class for Statistics
 */
class JWTStatistics {
public:
    static void incrementRefreshCount();
    static void incrementFailedRefreshCount();
    static void recordResponseTime(uint32_t timeMs);
    static void recordError(jwt_error_t error);
    static jwt_stats_t getSnapshot();
    static void reset();

private:
    static uint32_t totalRefreshes;
    static uint32_t failedRefreshes;
    static uint32_t totalResponseTime;
    static uint32_t responseCount;
    static jwt_error_t lastError;
    static SemaphoreHandle_t statsMutex;
};

/*
 * HTTP Status Codes for JWT API
 */
#define JWT_HTTP_OK                 200
#define JWT_HTTP_BAD_REQUEST        400
#define JWT_HTTP_UNAUTHORIZED       401
#define JWT_HTTP_FORBIDDEN          403
#define JWT_HTTP_NOT_FOUND          404
#define JWT_HTTP_TOO_MANY_REQUESTS  429
#define JWT_HTTP_INTERNAL_ERROR     500
#define JWT_HTTP_BAD_GATEWAY        502
#define JWT_HTTP_SERVICE_UNAVAILABLE 503

/*
 * WebSocket Message Types
 */
#define JWT_WS_MSG_AUTH_REFRESH     "auth/refresh"
#define JWT_WS_MSG_AUTH_OK          "auth/ok"
#define JWT_WS_MSG_AUTH_ERROR       "auth/error"

/*
 * Example Usage Documentation
 */
/*
// Initialize JWT Manager
JWTManager* jwt = JWTManager::getInstance();
if (!jwt->init()) {
    Serial.println("Failed to initialize JWT Manager");
    return;
}

// Set WebSocket refresh callback
jwt->setRefreshCallback([](const String& refreshMessage) -> bool {
    // Send refreshMessage via WebSocket
    return webSocketClient.sendText(refreshMessage);
});

// Set event callback for monitoring
jwt->setEventCallback([](const jwt_event_t* event) {
    Serial.printf("JWT Event: %d at %u\n", event->type, event->timestamp);
});

// Authenticate device
if (jwt->authenticateDevice("A1-B2-C3")) {
    Serial.println("Device authenticated successfully");
    
    // Token will auto-refresh 60 seconds before expiry
    // Use jwt->getCurrentToken() to get token for API calls
}

// Handle WebSocket messages
void onWebSocketMessage(const String& message) {
    // Parse message and check if it's an auth response
    DynamicJsonDocument doc(1024);
    deserializeJson(doc, message);
    
    String type = doc["type"];
    if (type == "auth/ok" || type == "auth/error") {
        jwt->handleRefreshResponse(message);
    }
}

// Get token for API calls
String token = jwt->getCurrentToken();
if (!token.isEmpty()) {
    httpClient.addHeader("Authorization", "Bearer " + token);
}

// Manual token refresh if needed
if (!jwt->isTokenValid()) {
    jwt->forceRefresh();
}

// Get statistics
jwt_stats_t stats = jwt->getStatistics();
Serial.printf("Token valid: %s, Retry count: %d\n", 
              stats.token_valid ? "YES" : "NO", stats.retry_count);
*/

#endif /* JWT_MANAGER_H */