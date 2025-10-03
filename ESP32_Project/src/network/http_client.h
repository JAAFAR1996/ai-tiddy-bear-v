#pragma once

#include <Arduino.h>
#include <WiFiClientSecure.h>
#include <WiFiClient.h>
#include "../config/device_config.h"

// HTTP Response structure
struct HttpResponse {
  bool success;
  int statusCode;
  String headers;
  String body;
  String error;
  
  HttpResponse() : success(false), statusCode(0) {}
};

/**
 * @brief Establish secure TLS connection with root CA validation
 * @param client WiFiClientSecure instance
 * @param host Domain name (required for SNI) - NEVER use IP address
 * @param port HTTPS port (typically 443)
 * @return true if connection successful, false otherwise
 * 
 * SECURITY REQUIREMENTS:
 * - Uses GTS Root R4 certificate pinning
 * - Requires domain name for SNI (Server Name Indication)
 * - Validates system time before connection
 * - NEVER uses setInsecure() or IP addresses
 * - 15-second connection timeout
 * 
 * BLOCKED IN PRODUCTION:
 * - setInsecure() calls
 * - IP address connections
 * - Connections without time sync
 */
bool connect_secure(WiFiClientSecure& client, const char* host, uint16_t port = 443);

/**
 * @brief Development-only insecure HTTP connection
 * @param client WiFiClient instance
 * @param host Server hostname
 * @param port HTTP port (typically 80)
 * @return true if connection successful
 * 
 * WARNING: This function is BLOCKED in production builds
 * Only available when DEVELOPMENT_BUILD is defined
 */
bool connect_insecure_development_only(WiFiClient& client, const char* host, uint16_t port = 80);

/**
 * @brief High-level secure HTTP client class
 * 
 * Provides a convenient interface for making HTTPS requests
 * with automatic certificate validation and proper timeouts.
 */
class SecureHttpClient {
private:
  WiFiClientSecure client;
  bool connected;
  String currentHost;
  uint16_t currentPort;
  String lastError;
  unsigned long requestTimeout;

public:
  SecureHttpClient();
  ~SecureHttpClient();
  
  /**
   * @brief Connect to HTTPS server
   * @param host Domain name (required for SNI)
   * @param port HTTPS port (default 443)
   * @return true if connection successful
   */
  bool connect(const char* host, uint16_t port = 443);
  
  /**
   * @brief Disconnect from server
   */
  void disconnect();
  
  /**
   * @brief Check if currently connected
   * @return true if connected and client is active
   */
  bool isConnected();
  
  /**
   * @brief Make GET request
   * @param path URL path (e.g., "/api/v1/data")
   * @param headers Additional HTTP headers
   * @return HttpResponse with status and body
   */
  HttpResponse get(const String& path, const String& headers = "");
  
  /**
   * @brief Make POST request
   * @param path URL path
   * @param headers Additional HTTP headers
   * @param body Request body (JSON, etc.)
   * @return HttpResponse with status and body
   */
  HttpResponse post(const String& path, const String& headers = "", const String& body = "");
  
  /**
   * @brief Make PUT request
   * @param path URL path
   * @param headers Additional HTTP headers
   * @param body Request body
   * @return HttpResponse with status and body
   */
  HttpResponse put(const String& path, const String& headers = "", const String& body = "");
  
  /**
   * @brief Set request timeout
   * @param timeout Timeout in milliseconds
   */
  void setTimeout(unsigned long timeout);
  
  /**
   * @brief Get last error message
   * @return Error description string
   */
  String getLastError() const;

private:
  HttpResponse makeRequest(const String& method, const String& path, 
                          const String& headers, const String& body);
};

/**
 * @brief Simple utility function for single secure request
 * @param host Server domain name
 * @param port HTTPS port
 * @param path Request path
 * @param response Output response body
 * @return true if request successful
 * 
 * Example:
 *   String response;
 *   if (makeSecureRequest("api.example.com", 443, "/status", response)) {
 *     Serial.println("Response: " + response);
 *   }
 */
bool makeSecureRequest(const char* host, uint16_t port, const String& path, String& response);

/**
 * @brief Failover-aware secure request using configured hosts
 * @param path Request path
 * @param response Output response body
 * @param maxRetries Maximum retry attempts across hosts
 * @return true if request successful
 * 
 * This function automatically:
 * - Uses current active host from device configuration
 * - Handles failover between primary/secondary hosts
 * - Implements exponential backoff on failures
 * - Reports success/failure for failover logic
 */
bool makeFailoverSecureRequest(const String& path, String& response, int maxRetries = 3);

/**
 * @brief High-level failover-aware HTTP client
 * 
 * Automatically manages connections to primary/secondary hosts
 * with intelligent failover and retry logic.
 */
class FailoverHttpClient {
private:
  SecureHttpClient httpClient;
  String lastUsedHost;
  uint16_t lastUsedPort;
  bool connected;

public:
  FailoverHttpClient();
  ~FailoverHttpClient();
  
  /**
   * @brief Connect using current configured host
   * @param forceReconnect Force new connection even if already connected
   * @return true if connection successful
   */
  bool connect(bool forceReconnect = false);
  
  /**
   * @brief Make GET request with automatic failover
   * @param path URL path
   * @param headers Additional headers
   * @param maxRetries Maximum retry attempts
   * @return HttpResponse with result
   */
  HttpResponse get(const String& path, const String& headers = "", int maxRetries = 3);
  
  /**
   * @brief Make POST request with automatic failover
   * @param path URL path
   * @param headers Additional headers
   * @param body Request body
   * @param maxRetries Maximum retry attempts
   * @return HttpResponse with result
   */
  HttpResponse post(const String& path, const String& headers = "", const String& body = "", int maxRetries = 3);
  
  /**
   * @brief Disconnect and cleanup
   */
  void disconnect();
  
  /**
   * @brief Check if ready for retry (respects backoff)
   * @return true if ready to retry
   */
  bool isReadyForRetry();

private:
  HttpResponse makeRequestWithFailover(const String& method, const String& path, 
                                     const String& headers, const String& body, int maxRetries);
  bool connectToCurrentHost();
};

// Security constants
#define TLS_CONNECT_TIMEOUT_MS 15000
#define HTTP_REQUEST_TIMEOUT_MS 10000
#define PRODUCTION_DOMAIN "ai-tiddy-bear-v-xuqy.onrender.com"
#define PRODUCTION_PORT 443

// Security validation macros
#ifdef PRODUCTION_BUILD
  #define VALIDATE_PRODUCTION_TLS(host, port) \
    do { \
      if (strcmp(host, PRODUCTION_DOMAIN) != 0) { \
        Serial.printf("⚠️  Production TLS warning: Non-production domain %s\n", host); \
      } \
      if (port != PRODUCTION_PORT) { \
        Serial.printf("⚠️  Production TLS warning: Non-standard port %d\n", port); \
      } \
    } while(0)
#else
  #define VALIDATE_PRODUCTION_TLS(host, port)
#endif