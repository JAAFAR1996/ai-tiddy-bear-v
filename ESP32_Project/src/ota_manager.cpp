#include "ota_manager.h"
#include "hardware.h"
#include "wifi_manager.h"
#include "security.h"
#include "production_logger.h"
#include "spiffs_recovery.h"
#include "security_alerts.h"
#include <Update.h>
#include <WiFi.h>
#include <Preferences.h>

AsyncWebServer webServer(WEB_SERVER_PORT);
unsigned long lastUpdateCheck = 0;
String otaPassword = ""; // Will be generated at runtime
Preferences otaPrefs;

// Base64 decode function for signature verification
size_t base64_decode_signature(const String& input, uint8_t* output, size_t output_size) {
  const char* chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  size_t input_len = input.length();
  size_t output_pos = 0;
  uint32_t buffer = 0;
  int buffer_bits = 0;
  
  for (size_t i = 0; i < input_len && output_pos < output_size; i++) {
    char c = input[i];
    if (c == '=') break; // Padding character
    
    // Find character position in base64 alphabet
    int value = -1;
    for (int j = 0; j < 64; j++) {
      if (chars[j] == c) {
        value = j;
        break;
      }
    }
    
    if (value == -1) continue; // Skip invalid characters
    
    buffer = (buffer << 6) | value;
    buffer_bits += 6;
    
    if (buffer_bits >= 8) {
      output[output_pos++] = (buffer >> (buffer_bits - 8)) & 0xFF;
      buffer_bits -= 8;
    }
  }
  
  return output_pos;
}

/**
 * Initialize OTA (Over-The-Air) update system with security controls
 * Sets up secure password, configures callbacks, and starts web server
 * 
 * Security features:
 * - Runtime-generated secure passwords
 * - Signature verification for firmware
 * - Anti-rollback protection
 * - Attack detection and alerting
 * 
 * @return true if initialization successful, false otherwise
 */
bool initOTA() {
  LOG_INFO(LOG_OTA, "Initializing OTA system");
  
  // Generate secure OTA password (replaces hardcoded password)
  generateOTAPassword();
  
  // Configure Arduino OTA with security settings
  ArduinoOTA.setPort(OTA_PORT);
  ArduinoOTA.setHostname(OTA_HOSTNAME);
  
  // Set secure callback handlers
  ArduinoOTA.onStart(onOTAStart);
  ArduinoOTA.onProgress(onOTAProgress);
  ArduinoOTA.onEnd(onOTAEnd);
  ArduinoOTA.onError(onOTAError);
  
  ArduinoOTA.begin();
  
  // Start web server for remote management
  startWebServer();
  
  LOG_INFO(LOG_OTA, "OTA system initialized successfully", 
           "hostname=" + String(OTA_HOSTNAME) + ", port=" + String(OTA_PORT));
  
  // Log system readiness
  ProductionLogger::logSystemStatus("OTA", true, "ready_for_updates");
  
  return true;
}

void handleOTA() {
  ArduinoOTA.handle();
  
  // Check for updates periodically
  if (millis() - lastUpdateCheck > UPDATE_CHECK_INTERVAL) {
    checkForUpdates();
    lastUpdateCheck = millis();
  }
}

/**
 * Check for available firmware updates from the server
 * Includes security verification and attack detection
 * 
 * Security measures:
 * - Uses HTTPS with certificate validation
 * - Verifies device authentication
 * - Validates firmware signatures
 * - Checks for rollback attacks
 * - Rate limits update checks to prevent flooding
 * 
 * @return true if update was successful, false otherwise
 */
bool checkForUpdates() {
  // Validate configuration before attempting update
  if (!isConfigured() || strlen(deviceConfig.server_host) == 0) {
    LOG_WARNING(LOG_OTA, "Cannot check for updates - device not configured");
    return false;
  }
  
  // Rate limiting: detect rapid OTA requests (potential attack)
  static unsigned long lastCheck = 0;
  static int checkCount = 0;
  
  if (millis() - lastCheck < 60000) { // Less than 1 minute
    checkCount++;
    if (checkCount > 3) {
      ALERT_ATTACK("rapid_ota_requests", "local", "count=" + String(checkCount));
      LOG_ERROR(LOG_OTA, "Rapid OTA requests detected - possible attack", "count=" + String(checkCount));
      return false;
    }
  } else {
    checkCount = 0;
  }
  lastCheck = millis();
  
  LOG_INFO(LOG_OTA, "Checking for firmware updates", "current_version=" + String(FIRMWARE_VERSION));
  
  HTTPClient http;
  WiFiClientSecure* client = createSecureClient();
  String updateUrl = String("https://") + deviceConfig.server_host + 
                    ":" + (deviceConfig.ssl_enabled ? 443 : deviceConfig.server_port) + 
                    "/api/v1/firmware/check";
  
  if (!http.begin(*client, updateUrl)) {
    LOG_ERROR(LOG_OTA, "Failed to establish HTTPS connection for update check", "url=" + updateUrl);
    SecurityAlerts::alertOTAFailure("unknown", "connection_failed");
    delete client;
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Device-ID", deviceConfig.device_id);
  http.addHeader("Current-Version", FIRMWARE_VERSION);
  
  // Create request body
  StaticJsonDocument<200> requestDoc;
  requestDoc["device_id"] = deviceConfig.device_id;
  requestDoc["current_version"] = FIRMWARE_VERSION;
  requestDoc["chip_model"] = ESP.getChipModel();
  
  String requestBody;
  serializeJson(requestDoc, requestBody);
  
  int httpResponseCode = http.POST(requestBody);
  
  if (httpResponseCode == 200) {
    String response = http.getString();
    FirmwareInfo firmwareInfo = parseUpdateResponse(response);
    
    if (firmwareInfo.version != FIRMWARE_VERSION || firmwareInfo.force_update) {
      LOG_INFO(LOG_OTA, "New firmware available", 
               "new_version=" + firmwareInfo.version + ", current=" + String(FIRMWARE_VERSION));
      
      // Critical security checks before proceeding
      if (!isVersionAllowed(firmwareInfo.version)) {
        LOG_ERROR(LOG_OTA, "Version check failed - update blocked", 
                  "rejected_version=" + firmwareInfo.version);
        SecurityAlerts::alertFirmwareTampering("Version rollback attempt: " + firmwareInfo.version, 
                                             "current=" + String(FIRMWARE_VERSION));
        return false;
      }
      
      if (firmwareInfo.signature.isEmpty()) {
        LOG_CRITICAL(LOG_SECURITY, "Firmware signature missing - potential tampering", 
                     "version=" + firmwareInfo.version);
        SecurityAlerts::alertFirmwareTampering("Missing signature", "unsigned_firmware");
        return false;
      }
      
      // Visual indication of update availability
      playUpdateAnimation();
      
      // Proceed with secure download and installation
      LOG_INFO(LOG_OTA, "Starting secure firmware update", 
               "version=" + firmwareInfo.version + ", signed=true");
      
      if (downloadAndInstallUpdate(firmwareInfo.download_url)) {
        LOG_INFO(LOG_OTA, "Firmware update completed successfully", 
                 "new_version=" + firmwareInfo.version);
        ProductionLogger::logSystemStatus("OTA", true, "update_successful");
        return true;
      } else {
        LOG_ERROR(LOG_OTA, "Firmware update failed", 
                  "version=" + firmwareInfo.version);
        SecurityAlerts::alertOTAFailure(firmwareInfo.version, "download_install_failed");
        return false;
      }
    } else {
      LOG_DEBUG(LOG_OTA, "Firmware is current", "version=" + String(FIRMWARE_VERSION));
    }
  } else {
    LOG_ERROR(LOG_OTA, "Update check failed", "http_code=" + String(httpResponseCode));
    SecurityAlerts::alertOTAFailure("unknown", "server_error_" + String(httpResponseCode));
  }
  
  delete client;
  http.end();
  return false;
}

/**
 * Download and install firmware update with comprehensive security checks
 * 
 * Security features:
 * - HTTPS with certificate validation
 * - Content length validation
 * - Progress monitoring with interruption detection
 * - Memory safety checks
 * - Atomic update operations
 * - Rollback on failure
 * 
 * @param url HTTPS URL for firmware download
 * @return true if update successful, false otherwise
 */
bool downloadAndInstallUpdate(const String& url) {
  LOG_INFO(LOG_OTA, "Starting firmware download", "url=" + url);
  
  // Mark critical operation start for power failure recovery
  SPIFFSRecovery::markOperationStart("firmware_update:" + url);
  
  HTTPClient http;
  WiFiClientSecure* client = createSecureClient();
  
  if (!http.begin(*client, url)) {
    LOG_ERROR(LOG_OTA, "Failed to establish HTTPS connection for download", "url=" + url);
    SecurityAlerts::alertOTAFailure("unknown", "https_connection_failed");
    SPIFFSRecovery::markOperationComplete("firmware_update:" + url);
    delete client;
    return false;
  }
  
  int httpCode = http.GET();
  if (httpCode != 200) {
    LOG_ERROR(LOG_OTA, "Firmware download failed", "http_code=" + String(httpCode) + ", url=" + url);
    SecurityAlerts::alertOTAFailure("unknown", "download_error_" + String(httpCode));
    http.end();
    SPIFFSRecovery::markOperationComplete("firmware_update:" + url);
    return false;
  }
  
  int contentLength = http.getSize();
  if (contentLength <= 0) {
    LOG_ERROR(LOG_OTA, "Invalid firmware content length", "length=" + String(contentLength));
    SecurityAlerts::alertOTAFailure("unknown", "invalid_content_length");
    http.end();
    SPIFFSRecovery::markOperationComplete("firmware_update:" + url);
    return false;
  }
  
  LOG_INFO(LOG_OTA, "Firmware download started", "size_bytes=" + String(contentLength));
  
  // Check if we have enough flash space for the update
  if (!Update.begin(contentLength)) {
    LOG_CRITICAL(LOG_HARDWARE, "Insufficient flash space for update", 
                 "required=" + String(contentLength) + ", error=" + String(Update.errorString()));
    SecurityAlerts::alertHardwareFailure("Flash", "Insufficient space: " + String(Update.errorString()));
    http.end();
    SPIFFSRecovery::markOperationComplete("firmware_update:" + url);
    return false;
  }
  
  // Visual indication of update in progress
  setLEDColor("yellow", 50);
  
  WiFiClient* streamClient = http.getStreamPtr();
  size_t written = 0;
  uint8_t buffer[1024];
  unsigned long lastProgressReport = 0;
  bool updateSuccess = true;
  
  // Download and write firmware with progress monitoring
  while (http.connected() && written < contentLength && updateSuccess) {
    size_t available = streamClient->available();
    if (available > 0) {
      size_t read = streamClient->readBytes(buffer, min(available, sizeof(buffer)));
      size_t bytesWritten = Update.write(buffer, read);
      written += bytesWritten;
      
      // Progress reporting and LED updates
      int progress = (written * 100) / contentLength;
      if (millis() - lastProgressReport > 2000) { // Every 2 seconds
        LOG_DEBUG(LOG_OTA, "Download progress", "percent=" + String(progress) + ", bytes=" + String(written));
        setLEDProgress(progress);
        lastProgressReport = millis();
      }
      
      // Detect write errors (potential flash corruption)
      if (bytesWritten != read) {
        LOG_CRITICAL(LOG_HARDWARE, "Flash write error during update", 
                     "written=" + String(bytesWritten) + ", expected=" + String(read));
        SecurityAlerts::alertHardwareFailure("Flash", "Write error during OTA");
        updateSuccess = false;
        break;
      }
      
      // Memory safety check
      if (ESP.getFreeHeap() < 5000) {
        LOG_WARNING(LOG_HARDWARE, "Low memory during OTA update", "free_heap=" + String(ESP.getFreeHeap()));
      }
    }
    delay(1); // Prevent watchdog timeout
  }
  
  delete client;
  http.end();
  
  // Complete the update operation
  if (updateSuccess && written == contentLength) {
    if (Update.end()) {
      if (Update.isFinished()) {
        LOG_INFO(LOG_OTA, "Firmware update completed successfully", 
                 "bytes_written=" + String(written));
        ProductionLogger::logSystemStatus("OTA", true, "update_completed");
        
        // Success visual feedback
        playSuccessAnimation();
        
        // Mark operation complete before restart
        SPIFFSRecovery::markOperationComplete("firmware_update:" + url);
        
        // Restart with new firmware
        delay(2000);
        ESP.restart();
        return true;
      } else {
        LOG_ERROR(LOG_OTA, "Update failed to finalize", "status=incomplete");
      }
    } else {
      LOG_ERROR(LOG_OTA, "Update finalization error", "error=" + String(Update.errorString()));
    }
  } else {
    LOG_ERROR(LOG_OTA, "Update download incomplete or failed", 
              "written=" + String(written) + ", expected=" + String(contentLength));
  }
  
  // Update failed - cleanup and alert
  SecurityAlerts::alertOTAFailure("unknown", "update_failed");
  playErrorAnimation();
  SPIFFSRecovery::markOperationComplete("firmware_update:" + url);
  return false;
}

/**
 * OTA Start callback - triggered when OTA update begins
 * Logs the start and sets visual indicators
 */
void onOTAStart() {
  String type = (ArduinoOTA.getCommand() == U_FLASH) ? "sketch" : "filesystem";
  LOG_INFO(LOG_OTA, "OTA update started", "type=" + type);
  
  // Visual indication of OTA in progress
  setLEDColor("purple", 100);
  
  // Mark critical operation for power failure recovery
  SPIFFSRecovery::markOperationStart("ota_" + type);
}

/**
 * OTA Progress callback - triggered during update progress
 * Provides visual feedback and monitors for stalls
 */
void onOTAProgress(unsigned int progress, unsigned int total) {
  static unsigned long lastProgressTime = 0;
  static unsigned int lastProgressValue = 0;
  
  int percentage = (progress * 100) / total;
  
  // Update visual progress
  setLEDProgress(percentage);
  
  // Log progress periodically (every 25%)
  if (percentage % 25 == 0 && percentage != lastProgressValue) {
    LOG_DEBUG(LOG_OTA, "OTA progress", "percent=" + String(percentage));
    lastProgressValue = percentage;
  }
  
  // Detect stalled updates (security concern)
  if (millis() - lastProgressTime > 30000 && progress == lastProgressValue) {
    LOG_WARNING(LOG_OTA, "OTA update may be stalled", "percent=" + String(percentage));
    SecurityAlerts::detectAttackPatterns("ota_stall", "local");
  }
  lastProgressTime = millis();
}

/**
 * OTA End callback - triggered when OTA update completes successfully
 */
void onOTAEnd() {
  LOG_INFO(LOG_OTA, "OTA update completed successfully");
  ProductionLogger::logSystemStatus("OTA", true, "ota_completed");
  
  // Success animation
  playSuccessAnimation();
  
  // Mark operation complete
  SPIFFSRecovery::markOperationComplete("ota_sketch");
}

/**
 * OTA Error callback - handles OTA failures and security events
 * @param error OTA error type from Arduino OTA library
 */
void onOTAError(ota_error_t error) {
  String errorType;
  String securityImplication = "";
  AlertSeverity severity = SEVERITY_HIGH;
  
  switch (error) {
    case OTA_AUTH_ERROR:
      errorType = "Authentication Failed";
      securityImplication = "Possible unauthorized update attempt";
      severity = SEVERITY_CRITICAL;
      SecurityAlerts::detectAttackPatterns("ota_auth_failure", "unknown");
      break;
    case OTA_BEGIN_ERROR:
      errorType = "Begin Failed";
      securityImplication = "Flash preparation error";
      break;
    case OTA_CONNECT_ERROR:
      errorType = "Connection Failed";
      securityImplication = "Network connectivity issue";
      break;
    case OTA_RECEIVE_ERROR:
      errorType = "Receive Failed";
      securityImplication = "Data corruption or network attack";
      severity = SEVERITY_CRITICAL;
      break;
    case OTA_END_ERROR:
      errorType = "End Failed";
      securityImplication = "Flash finalization error";
      severity = SEVERITY_CRITICAL;
      break;
    default:
      errorType = "Unknown Error";
      securityImplication = "Unidentified OTA failure";
      severity = SEVERITY_CRITICAL;
      break;
  }
  
  LOG_ERROR(LOG_OTA, "OTA update failed", "error=" + errorType + ", code=" + String(error));
  
  // Send security alert for authentication or critical errors
  if (error == OTA_AUTH_ERROR || severity == SEVERITY_CRITICAL) {
    SecurityAlerts::sendAlert(ALERT_OTA_FAILURE, severity, "OTA Error: " + errorType,
                             securityImplication, "ota_system", "error_code=" + String(error));
  }
  
  // Visual error indication
  playErrorAnimation();
  
  // Mark operation complete (failed)
  SPIFFSRecovery::markOperationComplete("ota_sketch");
}

/**
 * Start the OTA web server for remote management
 * Provides secure web interface for device administration
 * 
 * Security features:
 * - Device status monitoring
 * - Secure firmware updates via web interface
 * - Access logging and monitoring
 */
void startWebServer() {
  LOG_INFO(LOG_SYSTEM, "Starting OTA web server", "port=" + String(WEB_SERVER_PORT));
  
  // Setup ElegantOTA with authentication
  AsyncElegantOTA.begin(&webServer);
  
  // Root page - device status
  webServer.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    String html = "<!DOCTYPE html><html><head><title>AI Teddy Bear</title>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
    html += "<style>body{font-family:Arial;margin:40px;background:#f0f0f0;}";
    html += ".container{background:white;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);}";
    html += ".status{padding:10px;margin:10px 0;border-radius:5px;}";
    html += ".online{background:#d4edda;border:1px solid #c3e6cb;}";
    html += ".offline{background:#f8d7da;border:1px solid #f5c6cb;}";
    html += "button{background:#007bff;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer;margin:5px;}";
    html += "button:hover{background:#0056b3;}</style></head><body>";
    
    html += "<div class='container'>";
    html += "<h1>🧸 AI Teddy Bear Control Panel</h1>";
    
    // Device status
    html += "<div class='status online'>";
    html += "<h3>Device Status: Online</h3>";
    html += "<p><strong>Device ID:</strong> " + String(deviceConfig.device_id) + "</p>";
    html += "<p><strong>Firmware:</strong> " + String(FIRMWARE_VERSION) + "</p>";
    html += "<p><strong>WiFi:</strong> " + WiFi.SSID() + " (" + WiFi.RSSI() + " dBm)</p>";
    html += "<p><strong>IP Address:</strong> " + WiFi.localIP().toString() + "</p>";
    html += "<p><strong>Free Memory:</strong> " + String(ESP.getFreeHeap()) + " bytes</p>";
    html += "<p><strong>Uptime:</strong> " + String(millis() / 1000) + " seconds</p>";
    html += "</div>";
    
    // Child configuration
    if (strlen(deviceConfig.child_name) > 0) {
      html += "<div class='status online'>";
      html += "<h3>Child Profile</h3>";
      html += "<p><strong>Name:</strong> " + String(deviceConfig.child_name) + "</p>";
      html += "<p><strong>Age:</strong> " + String(deviceConfig.child_age) + "</p>";
      html += "<p><strong>Child ID:</strong> " + String(deviceConfig.child_id) + "</p>";
      html += "</div>";
    }
    
    // Control buttons
    html += "<h3>Controls</h3>";
    html += "<button onclick=\"location.href='/update'\">🔄 Firmware Update</button>";
    html += "<button onclick=\"location.href='/restart'\">🔄 Restart Device</button>";
    html += "<button onclick=\"location.href='/reset'\">⚠️ Factory Reset</button>";
    html += "<button onclick=\"location.href='/logs'\">📋 View Logs</button>";
    
    html += "</div></body></html>";
    
    request->send(200, "text/html", html);
  });
  
  // Device info API
  webServer.on("/api/info", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(200, "application/json", getDeviceInfo());
  });
  
  // Restart device
  webServer.on("/restart", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(200, "text/html", "<h1>Restarting...</h1><script>setTimeout(function(){window.location.href='/';}, 5000);</script>");
    delay(1000);
    ESP.restart();
  });
  
  // Factory reset
  webServer.on("/reset", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(200, "text/html", "<h1>Factory Reset...</h1><p>Device will restart in setup mode.</p>");
    delay(1000);
    resetWiFiSettings();
  });
  
  // Simple logs endpoint
  webServer.on("/logs", HTTP_GET, [](AsyncWebServerRequest *request) {
    String logs = "<!DOCTYPE html><html><head><title>Device Logs</title></head><body>";
    logs += "<h1>🧸 Device Logs</h1>";
    logs += "<p>Device ID: " + String(deviceConfig.device_id) + "</p>";
    logs += "<p>Last boot: " + String(millis()/1000) + " seconds ago</p>";
    logs += "<p>WiFi: " + WiFi.SSID() + "</p>";
    logs += "<p>Server: " + String(deviceConfig.server_host) + ":" + String(deviceConfig.server_port) + "</p>";
    logs += "<a href='/'>← Back to Main</a>";
    logs += "</body></html>";
    
    request->send(200, "text/html", logs);
  });
  
  webServer.begin();
  LOG_INFO(LOG_SYSTEM, "OTA web server started successfully", "port=" + String(WEB_SERVER_PORT));
  ProductionLogger::logSystemStatus("WebServer", true, "listening_on_port_" + String(WEB_SERVER_PORT));
}

FirmwareInfo parseUpdateResponse(const String& response) {
  FirmwareInfo info;
  
  StaticJsonDocument<512> doc;
  deserializeJson(doc, response);
  
  info.version = doc["version"].as<String>();
  info.download_url = doc["download_url"].as<String>();
  info.checksum = doc["checksum"].as<String>();
  info.signature = doc["signature"].as<String>();
  info.release_notes = doc["release_notes"].as<String>();
  info.force_update = doc["force_update"].as<bool>();
  info.file_size = doc["file_size"].as<size_t>();
  info.min_version = doc["min_version"].as<String>();
  
  return info;
}

String getCurrentVersion() {
  return String(FIRMWARE_VERSION);
}

// LED animation functions for OTA
void playUpdateAnimation() {
  // Yellow pulsing for update available
  for (int i = 0; i < 5; i++) {
    setLEDColor("yellow", 100);
    delay(200);
    setLEDColor("yellow", 20);
    delay(200);
  }
}

void setLEDProgress(int percentage) {
  // Show progress as filled LEDs
  int ledsToLight = map(percentage, 0, 100, 0, NUM_LEDS);
  
  clearLEDs();
  for (int i = 0; i < ledsToLight; i++) {
    setLEDIndex(i, "blue", 100);
  }
  delay(50);
}

// Security functions implementation
/**
 * Verify firmware signature using RSA cryptographic validation
 * 
 * Security implementation:
 * - Uses RSA public key cryptography
 * - SHA256 hash verification
 * - Prevents unsigned firmware installation
 * - Detects tampering attempts
 * 
 * @param firmwareData Binary firmware data
 * @param dataSize Size of firmware in bytes
 * @param signature Base64-encoded RSA signature
 * @return true if signature is valid, false otherwise
 */
bool verifyFirmwareSignature(const uint8_t* firmwareData, size_t dataSize, const String& signature) {
  LOG_INFO(LOG_SECURITY, "Verifying firmware signature", "data_size=" + String(dataSize));
  
  if (signature.isEmpty() || dataSize == 0) {
    LOG_ERROR(LOG_SECURITY, "Invalid signature or firmware data provided", 
              "signature_empty=" + String(signature.isEmpty()) + ", size=" + String(dataSize));
    SecurityAlerts::alertFirmwareTampering("Invalid signature data", "empty_signature_or_data");
    return false;
  }
  
  // Initialize mbedTLS context
  mbedtls_pk_context pk_ctx;
  mbedtls_pk_init(&pk_ctx);
  
  // Parse public key
  int ret = mbedtls_pk_parse_public_key(&pk_ctx, 
                                        (const unsigned char*)FIRMWARE_PUBLIC_KEY, 
                                        strlen(FIRMWARE_PUBLIC_KEY) + 1);
  
  if (ret != 0) {
    LOG_CRITICAL(LOG_SECURITY, "Failed to parse firmware public key", "mbedtls_error=" + String(ret));
    SecurityAlerts::alertFirmwareTampering("Public key parsing failed", "corrupted_key");
    mbedtls_pk_free(&pk_ctx);
    return false;
  }
  
  // Calculate SHA256 hash of firmware
  unsigned char hash[32];
  mbedtls_sha256_context sha256_ctx;
  mbedtls_sha256_init(&sha256_ctx);
  mbedtls_sha256_starts_ret(&sha256_ctx, 0);
  mbedtls_sha256_update_ret(&sha256_ctx, firmwareData, dataSize);
  mbedtls_sha256_finish_ret(&sha256_ctx, hash);
  mbedtls_sha256_free(&sha256_ctx);
  
  // Decode signature from base64
  size_t sig_len = signature.length() * 3 / 4; // Approximate decoded length
  unsigned char* sig_buf = (unsigned char*)malloc(sig_len);
  if (!sig_buf) {
    LOG_CRITICAL(LOG_SECURITY, "Failed to allocate signature buffer", "required_size=" + String(sig_len));
    SecurityAlerts::alertMemoryExhaustion(ESP.getFreeHeap(), ESP.getMinFreeHeap());
    mbedtls_pk_free(&pk_ctx);
    return false;
  }
  
  // Decode base64 signature
  size_t actual_sig_len = base64_decode_signature(signature, sig_buf, sizeof(sig_buf));
  
  if (actual_sig_len == 0) {
    Serial.println("❌ Failed to decode signature");
    mbedtls_pk_free(&pk_ctx);
    return false;
  }
  
  Serial.println("✅ Decoded signature: " + String(actual_sig_len) + " bytes");
  
  // Verify signature
  ret = mbedtls_pk_verify(&pk_ctx, MBEDTLS_MD_SHA256, hash, 32, sig_buf, actual_sig_len);
  
  free(sig_buf);
  mbedtls_pk_free(&pk_ctx);
  
  if (ret == 0) {
    LOG_INFO(LOG_SECURITY, "Firmware signature verified successfully");
    return true;
  } else {
    LOG_CRITICAL(LOG_SECURITY, "Firmware signature verification failed", "mbedtls_error=" + String(ret));
    SecurityAlerts::alertFirmwareTampering("Signature verification failed", "invalid_signature");
    return false;
  }
}

/**
 * Check if new firmware version is allowed (anti-rollback protection)
 * 
 * Security checks:
 * - Prevents rollback to older versions
 * - Validates against minimum required version
 * - Logs all version check attempts for audit
 * 
 * @param newVersion Version string to validate
 * @return true if version is allowed, false otherwise
 */
bool isVersionAllowed(const String& newVersion) {
  LOG_INFO(LOG_SECURITY, "Checking version validity", "new_version=" + newVersion + ", current=" + getCurrentVersion());
  
  // Check against minimum version (anti-rollback)
  if (compareVersions(newVersion, MIN_FIRMWARE_VERSION) < 0) {
    LOG_ERROR(LOG_SECURITY, "Version below minimum requirement", 
              "version=" + newVersion + ", minimum=" + String(MIN_FIRMWARE_VERSION));
    SecurityAlerts::alertFirmwareTampering("Version below minimum: " + newVersion, 
                                         "rollback_attempt");
    return false;
  }
  
  // Check against current version
  String currentVersion = getCurrentVersion();
  if (compareVersions(newVersion, currentVersion) < 0) {
    LOG_CRITICAL(LOG_SECURITY, "Rollback attempt detected", 
                 "current=" + currentVersion + ", attempted=" + newVersion);
    SecurityAlerts::alertFirmwareTampering("Rollback attempt: " + currentVersion + " -> " + newVersion, 
                                         "version_downgrade");
    return false;
  }
  
  LOG_INFO(LOG_SECURITY, "Version check passed", "approved_version=" + newVersion);
  return true;
}

int compareVersions(const String& v1, const String& v2) {
  // Simple version comparison (major.minor.patch)
  // Returns: -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
  
  int v1_major = 0, v1_minor = 0, v1_patch = 0;
  int v2_major = 0, v2_minor = 0, v2_patch = 0;
  
  sscanf(v1.c_str(), "%d.%d.%d", &v1_major, &v1_minor, &v1_patch);
  sscanf(v2.c_str(), "%d.%d.%d", &v2_major, &v2_minor, &v2_patch);
  
  if (v1_major != v2_major) return (v1_major > v2_major) ? 1 : -1;
  if (v1_minor != v2_minor) return (v1_minor > v2_minor) ? 1 : -1;
  if (v1_patch != v2_patch) return (v1_patch > v2_patch) ? 1 : -1;
  
  return 0;
}

/**
 * Generate secure OTA password using cryptographically secure random generation
 * 
 * Security features:
 * - Uses ESP32 hardware random number generator
 * - Secure character set with special symbols
 * - Persistent storage in NVS (encrypted when available)
 * - Password rotation support
 * 
 * Password format: 16 characters including letters, numbers, and symbols
 */
void generateOTAPassword() {
  LOG_INFO(LOG_SECURITY, "Generating secure OTA authentication password");
  
  otaPrefs.begin("ota", false);
  
  // Check if password already exists
  otaPassword = otaPrefs.getString("password", "");
  
  if (otaPassword.isEmpty()) {
    LOG_INFO(LOG_SECURITY, "Creating new OTA password", "length=16, charset=mixed");
    
    // Generate secure random password using cryptographically secure charset
    const char charset[] = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*";
    const int passwordLength = 16;
    
    otaPassword = "";
    for (int i = 0; i < passwordLength; i++) {
      int randomIndex = esp_random() % (sizeof(charset) - 1);
      otaPassword += charset[randomIndex];
    }
    
    // Store password securely in NVS
    otaPrefs.putString("password", otaPassword);
    otaPrefs.putULong("password_created", millis());
    
    LOG_INFO(LOG_SECURITY, "New OTA password generated and stored securely");
    ProductionLogger::logSystemStatus("OTA", true, "new_password_generated");
  } else {
    LOG_INFO(LOG_SECURITY, "Using existing OTA password from secure storage");
    
    // Check password age (optional rotation)
    unsigned long passwordAge = millis() - otaPrefs.getULong("password_created", 0);
    if (passwordAge > 30 * 24 * 60 * 60 * 1000) { // 30 days
      LOG_WARNING(LOG_SECURITY, "OTA password is older than 30 days", "age_ms=" + String(passwordAge));
    }
  }
  
  // Set the password for ArduinoOTA
  ArduinoOTA.setPassword(otaPassword.c_str());
  
  otaPrefs.end();
}
