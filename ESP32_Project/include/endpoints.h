#ifndef ENDPOINTS_H
#define ENDPOINTS_H

#include "config.h"

// ===== SERVER ENDPOINTS =====
// API base URL (scheme + host[:port]) for device HTTP requests (base, no /api suffix)
#define API_BASE_URL     "http://192.168.0.37"

#define API_PREFIX       "/api/v1/esp32"
#define CORE_PREFIX      "/api/v1/core"

// WebSocket endpoint paths (use new dedicated WS adapter)
#define WS_CONNECT_PATH  "/ws/esp32/connect"
#define WEBSOCKET_ENDPOINT "/ws/esp32/connect"   // Primary WebSocket
#define WEBSOCKET_AUDIO_ENDPOINT "/ws/esp32/connect"   // Unified endpoint
#define WEBSOCKET_COMMAND_ENDPOINT "/api/v1/esp32/commands"

// Device management endpoints - UPDATED PATHS
#define DEVICE_REGISTER_ENDPOINT   API_BASE_URL "/api/v1/esp32/devices/register"
#define DEVICE_STATUS_ENDPOINT "/api/v1/esp32/devices/%s/status"  // %s = device_id
#define DEVICE_HEARTBEAT_ENDPOINT "/api/v1/esp32/devices/%s/heartbeat"
#define DEVICE_CONFIG_ENDPOINT     API_BASE_URL "/api/v1/esp32/config"  // ✅ Public endpoint
#define DEVICE_CLAIM_ENDPOINT      API_BASE_URL "/api/v1/pair/claim"     // ✅ Claim endpoint

// Authentication endpoints - CORRECTED PATHS
#define AUTH_LOGIN_ENDPOINT "/api/v1/esp32/auth/device/login"
#define AUTH_REFRESH_ENDPOINT "/api/v1/esp32/auth/device/refresh"
#define AUTH_LOGOUT_ENDPOINT "/api/v1/esp32/auth/device/logout"
#define AUTH_VALIDATE_ENDPOINT "/api/v1/esp32/auth/device/validate"
#define AUTH_CLAIM_ENDPOINT "/api/v1/pair/claim"  // ✅ Device claiming

// Firmware and OTA endpoints - CORRECTED PATHS
#define FIRMWARE_MANIFEST_ENDPOINT "/api/v1/esp32/firmware"  // ✅ Public endpoint
#define FIRMWARE_CHECK_ENDPOINT "/api/v1/esp32/firmware/check"
#define FIRMWARE_DOWNLOAD_ENDPOINT "/api/v1/esp32/firmware/download/%s"  // %s = version
#define FIRMWARE_UPDATE_ENDPOINT "/api/v1/esp32/firmware/update"
#define OTA_STATUS_ENDPOINT "/api/v1/esp32/ota/status"

// Audio processing endpoints
#define AUDIO_UPLOAD_ENDPOINT "/audio/upload"
#define AUDIO_PROCESS_ENDPOINT "/audio/process"
#define AUDIO_TTS_ENDPOINT "/audio/tts"
#define AUDIO_STT_ENDPOINT "/audio/stt"

// Child safety endpoints
#define SAFETY_CHECK_ENDPOINT "/safety/check"
#define SAFETY_REPORT_ENDPOINT "/safety/report"
#define CONTENT_FILTER_ENDPOINT "/safety/content/filter"

// Parent dashboard endpoints
#define PARENT_DASHBOARD_ENDPOINT "/parent/dashboard"
#define PARENT_SETTINGS_ENDPOINT "/parent/settings"
#define PARENT_REPORTS_ENDPOINT "/parent/reports"

// Monitoring and logging endpoints
#define HEALTH_CHECK_ENDPOINT "/health"
#define METRICS_ENDPOINT "/metrics"
#define LOGS_UPLOAD_ENDPOINT "/logs/upload"
#define ERROR_REPORT_ENDPOINT "/errors/report"

// Emergency endpoints
#define EMERGENCY_ALERT_ENDPOINT "/emergency/alert"
#define PANIC_BUTTON_ENDPOINT "/emergency/panic"
#define SOS_ENDPOINT "/emergency/sos"

// ===== URL BUILDER FUNCTIONS =====
// Use these functions to build complete URLs

inline String buildDeviceURL(const char* endpoint, const String& deviceId) {
  String url = API_BASE_URL;
  char buffer[256];
  snprintf(buffer, sizeof(buffer), endpoint, deviceId.c_str());
  return url + buffer;
}

inline String buildFirmwareURL(const char* endpoint, const String& version) {
  String url = API_BASE_URL;
  char buffer[256];
  snprintf(buffer, sizeof(buffer), endpoint, version.c_str());
  return url + buffer;
}

inline String buildWebSocketURL(const char* endpoint) {
  String scheme = USE_SSL ? "wss" : "ws";
  String url = scheme + "://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + String(endpoint);
  return url;
}

inline String buildWebSocketURL() {
  return buildWebSocketURL(WEBSOCKET_ENDPOINT);
}

// ===== ENDPOINT VALIDATION =====
bool isValidEndpoint(const String& endpoint);
bool isSecureEndpoint(const String& endpoint);

// ===== API VERSIONING =====
#define API_VERSION_V1 "v1"
#define API_VERSION_V2 "v2"
#define CURRENT_API_VERSION API_VERSION_V1

// ===== TIMEOUT CONFIGURATIONS =====
#define HTTP_TIMEOUT_SHORT 5000      // 5 seconds
#define HTTP_TIMEOUT_MEDIUM 15000    // 15 seconds
#define HTTP_TIMEOUT_LONG 30000      // 30 seconds
#define WEBSOCKET_TIMEOUT 60000      // 60 seconds

// ===== RETRY CONFIGURATIONS =====
#define MAX_RETRY_ATTEMPTS 3
#define RETRY_DELAY_MS 1000
#define EXPONENTIAL_BACKOFF true

// ===== RATE LIMITING =====
#define MAX_REQUESTS_PER_MINUTE 60
#define MAX_AUDIO_UPLOADS_PER_HOUR 120
#define MAX_ERROR_REPORTS_PER_HOUR 10

#endif
