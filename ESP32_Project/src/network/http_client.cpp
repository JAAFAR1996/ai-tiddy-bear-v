#include "http_client.h"
#include "security/root_cert.h"
#include "time_sync.h"
#include <WiFiClientSecure.h>
#include <WiFi.h>

// HTTP client configuration constants
const uint16_t DEFAULT_HTTPS_PORT = 443;
const uint16_t DEFAULT_HTTP_PORT = 80;
const unsigned long TLS_CONNECT_TIMEOUT = 15000;  // 15 seconds
const unsigned long HTTP_REQUEST_TIMEOUT = 10000; // 10 seconds
const unsigned long DNS_TIMEOUT = 5000;          // 5 seconds

bool connect_secure(WiFiClientSecure& client, const char* host, uint16_t port) {
  Serial.printf("🔒 Establishing secure TLS connection to %s:%d\n", host, port);
  
  // ✅ Critical: Validate time before any TLS connection
  if (!isTimeSynced()) {
    Serial.println("❌ TLS connection blocked: Time not synchronized");
    return false;
  }
  
  // ✅ Critical: Verify WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ TLS connection failed: No WiFi connection");
    return false;
  }
  
  // ✅ Set root CA certificate (NO setInsecure() allowed)
  Serial.println("📋 Setting GTS Root R4 certificate...");
  client.setCACert(ROOT_CA_PEM);
  
  // ✅ Set connection timeout
  client.setTimeout(TLS_CONNECT_TIMEOUT);
  
  // ✅ Production security validation
  #ifdef PRODUCTION_BUILD
    // Verify we're using the production domain
    if (strcmp(host, "ai-tiddy-bear-v-xuqy.onrender.com") != 0) {
      Serial.printf("⚠️  Production warning: Connecting to non-production host: %s\n", host);
    }
    
    // Ensure HTTPS port
    if (port != 443) {
      Serial.printf("⚠️  Production warning: Non-standard HTTPS port: %d\n", port);
    }
  #endif
  
  // ✅ Perform DNS resolution first (for debugging)
  IPAddress serverIP;
  if (!WiFi.hostByName(host, serverIP)) {
    Serial.printf("❌ DNS resolution failed for %s\n", host);
    return false;
  }
  Serial.printf("📍 Resolved %s to %s\n", host, serverIP.toString().c_str());
  
  // ✅ Critical: Connect using domain name for SNI (NEVER use IP)
  Serial.printf("🔗 Connecting with SNI to %s:%d...\n", host, port);
  
  unsigned long connectStart = millis();
  bool connected = client.connect(host, port);
  unsigned long connectTime = millis() - connectStart;
  
  if (connected) {
    // ✅ Unified success logging
    Serial.printf("[TLS] ok host=%s port=%d time=%lums\n", 
                  host, port, connectTime);
    
    // Additional connection validation
    if (!client.connected()) {
      Serial.printf("[TLS] fail host=%s port=%d code=handshake reason=connection_lost\n", host, port);
      return false;
    }
    
    return true;
  } else {
    // ✅ Unified failure logging - determine failure reason
    String reason = "unknown";
    
    // Analyze potential failure reasons
    if (connectTime < 1000) {
      reason = "timeout_early";  // Very quick failure, likely network/DNS
    } else if (connectTime > 10000) {
      reason = "timeout_late";   // Long delay, likely TLS handshake timeout
    } else {
      reason = "handshake";      // Mid-range, likely certificate/handshake issue
    }
    
    Serial.printf("[TLS] fail host=%s port=%d code=connect reason=%s time=%lums\n", 
                  host, port, reason.c_str(), connectTime);
    
    return false;
  }
}

bool connect_insecure_development_only(WiFiClient& client, const char* host, uint16_t port) {
  #ifdef PRODUCTION_BUILD
    Serial.println("❌ SECURITY VIOLATION: Insecure connections blocked in production");
    return false;
  #endif
  
  #ifdef DEVELOPMENT_BUILD
    Serial.printf("⚠️  [DEV ONLY] Insecure HTTP connection to %s:%d\n", host, port);
    client.setTimeout(HTTP_REQUEST_TIMEOUT);
    return client.connect(host, port);
  #else
    Serial.println("❌ Insecure connections only allowed in development builds");
    return false;
  #endif
}

SecureHttpClient::SecureHttpClient() : 
  connected(false), 
  lastError(""),
  requestTimeout(HTTP_REQUEST_TIMEOUT) {
}

SecureHttpClient::~SecureHttpClient() {
  disconnect();
}

bool SecureHttpClient::connect(const char* host, uint16_t port) {
  if (connected) {
    disconnect();
  }
  
  currentHost = String(host);
  currentPort = port;
  
  connected = connect_secure(client, host, port);
  
  if (!connected) {
    lastError = "TLS connection failed";
  } else {
    lastError = "";
  }
  
  return connected;
}

void SecureHttpClient::disconnect() {
  if (connected) {
    client.stop();
    connected = false;
  }
}

bool SecureHttpClient::isConnected() {
  if (!connected) return false;
  
  // Check actual connection status
  bool clientConnected = client.connected();
  if (!clientConnected) {
    connected = false;
  }
  
  return clientConnected;
}

HttpResponse SecureHttpClient::get(const String& path, const String& headers) {
  return makeRequest("GET", path, headers, "");
}

HttpResponse SecureHttpClient::post(const String& path, const String& headers, const String& body) {
  return makeRequest("POST", path, headers, body);
}

HttpResponse SecureHttpClient::put(const String& path, const String& headers, const String& body) {
  return makeRequest("PUT", path, headers, body);
}

HttpResponse SecureHttpClient::makeRequest(const String& method, const String& path, const String& headers, const String& body) {
  HttpResponse response;
  response.success = false;
  response.statusCode = 0;
  
  if (!isConnected()) {
    response.error = "Not connected to server";
    lastError = response.error;
    return response;
  }
  
  // Build HTTP request
  String request = method + " " + path + " HTTP/1.1\r\n";
  request += "Host: " + currentHost + "\r\n";
  request += "User-Agent: ESP32-TeddyBear/1.0\r\n";
  request += "Connection: close\r\n";
  
  if (headers.length() > 0) {
    request += headers;
    if (!headers.endsWith("\r\n")) {
      request += "\r\n";
    }
  }
  
  if (body.length() > 0) {
    request += "Content-Length: " + String(body.length()) + "\r\n";
    request += "Content-Type: application/json\r\n";
  }
  
  request += "\r\n";
  if (body.length() > 0) {
    request += body;
  }
  
  // Send request
  Serial.printf("📤 Sending %s %s\n", method.c_str(), path.c_str());
  client.print(request);
  
  // Read response with timeout
  unsigned long requestStart = millis();
  String responseText = "";
  
  while (client.connected() && (millis() - requestStart) < requestTimeout) {
    if (client.available()) {
      responseText += client.readString();
      break;
    }
    delay(10);
  }
  
  if (responseText.length() == 0) {
    response.error = "No response received";
    lastError = response.error;
    return response;
  }
  
  // Parse response
  int headerEnd = responseText.indexOf("\r\n\r\n");
  if (headerEnd == -1) {
    response.error = "Invalid HTTP response format";
    lastError = response.error;
    return response;
  }
  
  String headerSection = responseText.substring(0, headerEnd);
  response.body = responseText.substring(headerEnd + 4);
  
  // Extract status code
  int statusStart = headerSection.indexOf(" ") + 1;
  int statusEnd = headerSection.indexOf(" ", statusStart);
  if (statusStart > 0 && statusEnd > statusStart) {
    response.statusCode = headerSection.substring(statusStart, statusEnd).toInt();
  }
  
  // Extract headers
  response.headers = headerSection;
  
  response.success = (response.statusCode >= 200 && response.statusCode < 300);
  
  if (!response.success) {
    response.error = "HTTP " + String(response.statusCode);
    lastError = response.error;
  }
  
  Serial.printf("📥 Response: %d (%d bytes)\n", response.statusCode, response.body.length());
  
  return response;
}

void SecureHttpClient::setTimeout(unsigned long timeout) {
  requestTimeout = timeout;
  if (connected) {
    client.setTimeout(timeout);
  }
}

String SecureHttpClient::getLastError() const {
  return lastError;
}

// Global utility functions for backward compatibility
bool makeSecureRequest(const char* host, uint16_t port, const String& path, String& response) {
  SecureHttpClient httpClient;
  
  if (!httpClient.connect(host, port)) {
    Serial.printf("❌ Failed to connect to %s:%d\n", host, port);
    return false;
  }
  
  HttpResponse httpResponse = httpClient.get(path);
  
  if (httpResponse.success) {
    response = httpResponse.body;
    return true;
  } else {
    Serial.printf("❌ HTTP request failed: %s\n", httpResponse.error.c_str());
    return false;
  }
}

bool makeFailoverSecureRequest(const String& path, String& response, int maxRetries) {
  FailoverHttpClient client;
  HttpResponse httpResponse = client.get(path, "", maxRetries);
  
  if (httpResponse.success) {
    response = httpResponse.body;
    return true;
  }
  
  return false;
}

// FailoverHttpClient implementation
FailoverHttpClient::FailoverHttpClient() : lastUsedPort(0), connected(false) {
}

FailoverHttpClient::~FailoverHttpClient() {
  disconnect();
}

bool FailoverHttpClient::connect(bool forceReconnect) {
  if (connected && !forceReconnect) {
    // Check if still connected to same host
    const char* currentHost = getActiveServerHost();
    uint16_t currentPort = getActiveServerPort();
    
    if (lastUsedHost.equals(currentHost) && lastUsedPort == currentPort && httpClient.isConnected()) {
      return true; // Already connected to correct host
    }
  }
  
  return connectToCurrentHost();
}

bool FailoverHttpClient::connectToCurrentHost() {
  const char* host = getActiveServerHost();
  uint16_t port = getActiveServerPort();
  
  // Check if ready for retry
  if (!deviceConfigManager.isReadyForRetry()) {
    unsigned long delay = deviceConfigManager.getNextRetryDelay();
    Serial.printf("⏳ Waiting %lu ms before retry...\n", delay);
    return false;
  }
  
  Serial.printf("🔗 Connecting to active server: %s:%d\n", host, port);
  
  disconnect(); // Clean disconnect first
  
  if (httpClient.connect(host, port)) {
    connected = true;
    lastUsedHost = String(host);
    lastUsedPort = port;
    
    // Report success for failover tracking
    reportServerSuccess(host);
    
    Serial.printf("✅ Connected to %s:%d\n", host, port);
    return true;
  } else {
    connected = false;
    
    // Report failure for failover tracking
    bool shouldFailover = reportServerFailure(host);
    
    if (shouldFailover) {
      Serial.println("🔄 Failover triggered, will try secondary on next attempt");
    }
    
    Serial.printf("❌ Connection failed to %s:%d\n", host, port);
    return false;
  }
}

HttpResponse FailoverHttpClient::get(const String& path, const String& headers, int maxRetries) {
  return makeRequestWithFailover("GET", path, headers, "", maxRetries);
}

HttpResponse FailoverHttpClient::post(const String& path, const String& headers, const String& body, int maxRetries) {
  return makeRequestWithFailover("POST", path, headers, body, maxRetries);
}

void FailoverHttpClient::disconnect() {
  if (connected) {
    httpClient.disconnect();
    connected = false;
  }
}

bool FailoverHttpClient::isReadyForRetry() {
  return deviceConfigManager.isReadyForRetry();
}

HttpResponse FailoverHttpClient::makeRequestWithFailover(const String& method, const String& path, 
                                                       const String& headers, const String& body, int maxRetries) {
  HttpResponse response;
  response.success = false;
  response.error = "No attempts made";
  
  for (int attempt = 0; attempt < maxRetries; attempt++) {
    Serial.printf("🔄 Attempt %d/%d for %s %s\n", attempt + 1, maxRetries, method.c_str(), path.c_str());
    
    // Ensure we're connected to the current active host
    if (!connect(attempt > 0)) { // Force reconnect on retry attempts
      response.error = "Connection failed";
      
      // Wait for backoff delay before next attempt
      if (attempt < maxRetries - 1) {
        unsigned long backoff = deviceConfigManager.getNextRetryDelay();
        Serial.printf("⏳ Waiting %lu ms before next attempt...\n", backoff);
        delay(min(backoff, 5000UL)); // Cap delay to 5 seconds for responsiveness
      }
      continue;
    }
    
    // Make the request
    if (method == "GET") {
      response = httpClient.get(path, headers);
    } else if (method == "POST") {
      response = httpClient.post(path, headers, body);
    } else if (method == "PUT") {
      response = httpClient.put(path, headers, body);
    } else {
      response.error = "Unsupported HTTP method";
      break;
    }
    
    if (response.success) {
      // Success - report to failover system
      reportServerSuccess(getActiveServerHost());
      Serial.printf("✅ Request successful on attempt %d\n", attempt + 1);
      break;
    } else {
      // Failure - report to failover system
      bool shouldFailover = reportServerFailure(getActiveServerHost());
      
      Serial.printf("❌ Request failed on attempt %d: %s\n", attempt + 1, response.error.c_str());
      
      if (shouldFailover && attempt < maxRetries - 1) {
        Serial.println("🔄 Attempting failover...");
        connected = false; // Force reconnection to new host
      }
    }
  }
  
  if (!response.success) {
    Serial.printf("❌ All %d attempts failed. Last error: %s\n", maxRetries, response.error.c_str());
  }
  
  return response;
}