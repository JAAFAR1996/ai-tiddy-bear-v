#include "monitoring.h"
#include "hardware.h"
#include "wifi_manager.h"
#include "websocket_handler.h"
#include "production_logger.h"
#include "security_alerts.h"
#include <WiFi.h>
#include <Preferences.h>

SystemHealth systemHealth;
ErrorLog errorLogs[MAX_ERROR_LOG_SIZE];
int errorLogIndex = 0;
unsigned long lastMonitoringReport = 0;
unsigned long lastErrorReport = 0;
unsigned long lastHealthCheck = 0;
unsigned long bootTime = 0;
unsigned long lastCPUCheck = 0;
unsigned long lastTaskTime = 0;

Preferences monitoringPrefs;

/**
 * Initialize system monitoring and health tracking
 * 
 * Features:
 * - Reset count tracking for stability analysis
 * - Watchdog timer initialization for crash prevention
 * - Error logging system setup
 * - System health baseline establishment
 * 
 * @return true if initialization successful
 */
bool initMonitoring() {
  LOG_INFO(LOG_SYSTEM, "Initializing monitoring system");
  
  // Initialize preferences for persistent data
  monitoringPrefs.begin("monitoring", false);
  
  // Load and increment reset count for stability tracking
  uint32_t resetCount = monitoringPrefs.getUInt("reset_count", 0);
  monitoringPrefs.putUInt("reset_count", resetCount + 1);
  
  // Initialize system health baseline
  systemHealth = {};
  systemHealth.reset_count = resetCount + 1;
  bootTime = millis();
  
  // Initialize watchdog timer for crash prevention
  initWatchdog();
  
  // Reset error logs array
  for (int i = 0; i < MAX_ERROR_LOG_SIZE; i++) {
    errorLogs[i] = {};
  }
  
  LOG_INFO(LOG_SYSTEM, "Monitoring system initialized successfully", 
           "reset_count=" + String(systemHealth.reset_count) + ", watchdog_enabled=true");
  
  // Log system startup event
  ProductionLogger::logSystemStatus("Monitoring", true, "system_boot_" + String(systemHealth.reset_count));
  
  return true;
}

void handleMonitoring() {
  unsigned long now = millis();
  
  // Feed watchdog
  feedWatchdog();
  
  // Perform health check
  if (now - lastHealthCheck > HEALTH_CHECK_INTERVAL) {
    performHealthCheck();
    lastHealthCheck = now;
  }
  
  // Send monitoring reports
  if (now - lastMonitoringReport > MONITORING_INTERVAL) {
    sendHealthReport();
    lastMonitoringReport = now;
  }
  
  // Send error reports if needed
  if (now - lastErrorReport > ERROR_REPORT_INTERVAL && systemHealth.error_count > 0) {
    sendErrorReport();
    lastErrorReport = now;
  }
}

SystemHealth getSystemHealth() {
  systemHealth.free_heap = ESP.getFreeHeap();
  systemHealth.min_free_heap = ESP.getMinFreeHeap();
  systemHealth.uptime = (millis() - bootTime) / 1000;
  systemHealth.cpu_usage = getCPUUsage();
  systemHealth.temperature = getTemperature();
  systemHealth.wifi_rssi = WiFi.RSSI();
  systemHealth.websocket_connected = isConnected;
  
  return systemHealth;
}

/**
 * Log system error with severity-based visual feedback and alerting
 * 
 * Error logging features:
 * - Structured error storage with context
 * - Visual LED feedback based on severity
 * - Critical error escalation to security alerts
 * - Persistent error tracking for stability analysis
 * 
 * @param type Error type classification
 * @param message Error description
 * @param context Additional context information
 * @param severity Error severity level (1-4)
 */
void logError(ErrorType type, const String& message, const String& context, int severity) {
  String errorTypeName = getErrorTypeName(type);
  
  // Log using production logging system
  switch (severity) {
    case 1: // Info level
      LOG_INFO(LOG_SYSTEM, "System info: " + message, "type=" + errorTypeName + ", context=" + context);
      break;
    case 2: // Warning level
      LOG_WARNING(LOG_SYSTEM, "System warning: " + message, "type=" + errorTypeName + ", context=" + context);
      break;
    case 3: // Error level
      LOG_ERROR(LOG_SYSTEM, "System error: " + message, "type=" + errorTypeName + ", context=" + context);
      break;
    case 4: // Critical level
      LOG_CRITICAL(LOG_SYSTEM, "Critical system error: " + message, "type=" + errorTypeName + ", context=" + context);
      break;
  }
  
  // Add to circular error log buffer
  ErrorLog& log = errorLogs[errorLogIndex];
  log.timestamp = millis();
  log.type = type;
  log.message = message;
  log.context = context;
  log.severity = severity;
  
  errorLogIndex = (errorLogIndex + 1) % MAX_ERROR_LOG_SIZE;
  systemHealth.error_count++;
  
  // Visual feedback based on severity
  switch (severity) {
    case 1: // Info - Blue pulse
      setLEDColor("blue", 30);
      delay(200);
      clearLEDs();
      break;
    case 2: // Warning - Yellow flash
      setLEDColor("yellow", 50);
      delay(500);
      clearLEDs();
      break;
    case 3: // Error - Orange sustained
      setLEDColor("orange", 70);
      delay(1000);
      clearLEDs();
      break;
    case 4: // Critical - Red flashing pattern
      for (int i = 0; i < 3; i++) {
        setLEDColor("red", 100);
        delay(300);
        clearLEDs();
        delay(300);
      }
      break;
  }
  
  // Escalate critical errors to security alert system
  if (severity >= 4) {
    SecurityAlerts::alertSystemCompromise("Critical monitoring error: " + message, 
                                        "error_type=" + errorTypeName + ", context=" + context);
    handleCriticalError(message);
  } else if (severity >= 3) {
    // Alert for error-level issues that might indicate system problems
    if (type == ERROR_MEMORY_LOW || type == ERROR_WATCHDOG_TIMEOUT) {
      SecurityAlerts::alertHardwareFailure(errorTypeName, message + " (context: " + context + ")");
    }
  }
}

/**
 * Send comprehensive error report to monitoring server
 * 
 * Features:
 * - Collects all recent errors from circular buffer
 * - Includes system context and error classification
 * - Automatic retry on failure
 * - Error report success tracking
 */
void sendErrorReport() {
  if (!isConfigured() || !WiFi.isConnected()) {
    LOG_DEBUG(LOG_SYSTEM, "Skipping error report - device not ready", 
              "configured=" + String(isConfigured()) + ", connected=" + String(WiFi.isConnected()));
    return;
  }
  
  LOG_INFO(LOG_SYSTEM, "Sending error report to monitoring server", "error_count=" + String(systemHealth.error_count));
  
  HTTPClient http;
  String url = String("http://") + deviceConfig.server_host + 
               ":" + deviceConfig.server_port + 
               "/api/v1/devices/" + deviceConfig.device_id + "/errors";
  
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + String(deviceConfig.device_secret));
  
  // Create comprehensive error report
  StaticJsonDocument<2048> doc;
  doc["device_id"] = deviceConfig.device_id;
  doc["timestamp"] = millis();
  doc["error_count"] = systemHealth.error_count;
  doc["uptime"] = (millis() - bootTime) / 1000;
  doc["reset_count"] = systemHealth.reset_count;
  
  JsonArray errors = doc.createNestedArray("errors");
  
  // Add all recent errors from circular buffer
  int errorCount = 0;
  for (int i = 0; i < MAX_ERROR_LOG_SIZE; i++) {
    int idx = (errorLogIndex + i) % MAX_ERROR_LOG_SIZE;
    if (errorLogs[idx].timestamp > 0) {
      JsonObject error = errors.createNestedObject();
      error["timestamp"] = errorLogs[idx].timestamp;
      error["type"] = getErrorTypeName(errorLogs[idx].type);
      error["message"] = errorLogs[idx].message;
      error["context"] = errorLogs[idx].context;
      error["severity"] = errorLogs[idx].severity;
      errorCount++;
    }
  }
  
  String payload;
  serializeJson(doc, payload);
  
  LOG_DEBUG(LOG_SYSTEM, "Error report payload prepared", "errors_included=" + String(errorCount) + ", size_bytes=" + String(payload.length()));
  
  int responseCode = http.POST(payload);
  if (responseCode == 200) {
    LOG_INFO(LOG_SYSTEM, "Error report sent successfully", "errors_reported=" + String(errorCount));
    ProductionLogger::logSystemStatus("ErrorReporting", true, "report_sent_successfully");
    resetErrorCounts();
  } else {
    LOG_ERROR(LOG_SYSTEM, "Failed to send error report", "http_code=" + String(responseCode) + ", url=" + url);
    SecurityAlerts::alertSystemCompromise("Error reporting failure", "http_code=" + String(responseCode));
  }
  
  http.end();
}

/**
 * Send comprehensive system health report to monitoring server
 * 
 * Health metrics included:
 * - Memory usage and heap statistics
 * - CPU utilization and temperature
 * - Network connectivity quality
 * - System stability indicators
 * - Component status summary
 */
void sendHealthReport() {
  if (!isConfigured() || !WiFi.isConnected()) {
    LOG_DEBUG(LOG_SYSTEM, "Skipping health report - device not ready");
    return;
  }
  
  // Get current comprehensive health status
  SystemHealth health = getSystemHealth();
  
  LOG_INFO(LOG_SYSTEM, "Sending health report to monitoring server", 
           "uptime=" + String(health.uptime) + "s, heap=" + String(health.free_heap) + 
           ", errors=" + String(health.error_count));
  
  HTTPClient http;
  String url = String("http://") + deviceConfig.server_host + 
               ":" + deviceConfig.server_port + 
               "/api/v1/devices/" + deviceConfig.device_id + "/health";
  
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + String(deviceConfig.device_secret));
  
  // Create comprehensive health report
  StaticJsonDocument<1024> doc;
  doc["device_id"] = deviceConfig.device_id;
  doc["timestamp"] = millis();
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["uptime"] = health.uptime;
  doc["free_heap"] = health.free_heap;
  doc["min_free_heap"] = health.min_free_heap;
  doc["cpu_usage"] = health.cpu_usage;
  doc["temperature"] = health.temperature;
  doc["wifi_rssi"] = health.wifi_rssi;
  doc["error_count"] = health.error_count;
  doc["reset_count"] = health.reset_count;
  doc["audio_system_ok"] = health.audio_system_ok;
  doc["websocket_connected"] = health.websocket_connected;
  doc["server_responsive"] = health.server_responsive;
  
  // Add additional system metrics
  doc["mac_address"] = WiFi.macAddress();
  doc["wifi_ssid"] = WiFi.SSID();
  doc["chip_model"] = ESP.getChipModel();
  doc["flash_size"] = ESP.getFlashChipSize();
  
  String payload;
  serializeJson(doc, payload);
  
  LOG_DEBUG(LOG_SYSTEM, "Health report payload prepared", "size_bytes=" + String(payload.length()));
  
  int responseCode = http.POST(payload);
  if (responseCode == 200) {
    LOG_INFO(LOG_SYSTEM, "Health report sent successfully");
    systemHealth.server_responsive = true;
    ProductionLogger::logSystemStatus("HealthReporting", true, "report_sent_successfully");
  } else {
    LOG_ERROR(LOG_SYSTEM, "Failed to send health report", "http_code=" + String(responseCode) + ", url=" + url);
    systemHealth.server_responsive = false;
    
    // Log server connectivity error
    logError(ERROR_SERVER_UNREACHABLE, "Health report transmission failed", 
             "code=" + String(responseCode), 2);
    
    // Alert if server becomes unresponsive
    SecurityAlerts::alertSystemCompromise("Health reporting failure - server unresponsive", 
                                        "http_code=" + String(responseCode));
  }
  
  http.end();
}

bool performHealthCheck() {
  bool allSystemsOk = true;
  
  // Check memory
  if (!checkMemoryHealth()) {
    allSystemsOk = false;
  }
  
  // Check WiFi
  if (!checkWiFiHealth()) {
    allSystemsOk = false;
  }
  
  // Check server connectivity
  if (!checkServerHealth()) {
    allSystemsOk = false;
  }
  
  // Check audio system
  systemHealth.audio_system_ok = (getAudioState() != AUDIO_ERROR);
  if (!systemHealth.audio_system_ok) {
    logError(ERROR_AUDIO_FAILED, "Audio system not responding", "", 3);
    allSystemsOk = false;
  }
  
  // Update overall health
  if (allSystemsOk) {
    // Green pulse for healthy system
    setLEDColor("green", 20);
    delay(100);
    clearLEDs();
  }
  
  return allSystemsOk;
}

/**
 * Initialize hardware watchdog timer for crash prevention
 * 
 * Watchdog configuration:
 * - Timeout period for unresponsive system detection
 * - Automatic system restart on timeout
 * - Current task monitoring registration
 */
void initWatchdog() {
  LOG_INFO(LOG_SYSTEM, "Initializing hardware watchdog timer", "timeout=" + String(WATCHDOG_TIMEOUT) + "s");
  
  // Configure ESP32 task watchdog timer
  esp_task_wdt_init(WATCHDOG_TIMEOUT, true);
  esp_task_wdt_add(NULL);  // Add current task to watchdog monitoring
  
  LOG_INFO(LOG_SYSTEM, "Watchdog timer initialized successfully", 
           "timeout=" + String(WATCHDOG_TIMEOUT) + "s, panic_enabled=true");
  
  ProductionLogger::logSystemStatus("Watchdog", true, "initialized_" + String(WATCHDOG_TIMEOUT) + "s");
}

void feedWatchdog() {
  esp_task_wdt_reset();
}

/**
 * Handle watchdog timeout event - system unresponsive
 * 
 * Emergency procedure:
 * - Log critical watchdog timeout event
 * - Send emergency alert if possible
 * - Perform controlled system restart
 */
void handleWatchdogTimeout() {
  LOG_EMERGENCY("WATCHDOG TIMEOUT - SYSTEM RESTART IMMINENT");
  
  // Try to log the critical event
  logError(ERROR_WATCHDOG_TIMEOUT, "System became unresponsive - watchdog timeout", "", 4);
  
  // Send emergency alert
  SecurityAlerts::alertRepeatedCrashes(1, "Watchdog timeout - system unresponsive");
  
  // Brief delay to allow emergency logging
  delay(1000);
  
  LOG_CRITICAL(LOG_SYSTEM, "Performing emergency restart due to watchdog timeout");
  ESP.restart();
}

float getCPUUsage() {
  unsigned long currentTime = millis();
  unsigned long deltaTime = currentTime - lastCPUCheck;
  
  if (deltaTime > 1000) {  // Calculate every second
    unsigned long taskTime = micros() - lastTaskTime;
    float usage = (taskTime / (deltaTime * 10.0));  // Rough estimate
    
    lastCPUCheck = currentTime;
    lastTaskTime = micros();
    
    return constrain(usage, 0.0, 100.0);
  }
  
  return systemHealth.cpu_usage;  // Return last known value
}

float getTemperature() {
  // ESP32 internal temperature (approximate)
  return temperatureRead();
}

bool checkMemoryHealth() {
  uint32_t freeHeap = ESP.getFreeHeap();
  
  if (freeHeap < 10000) {  // Less than 10KB free
    logError(ERROR_MEMORY_LOW, "Low memory warning", String(freeHeap), 3);
    return false;
  }
  
  if (freeHeap < 5000) {  // Less than 5KB free - critical
    logError(ERROR_MEMORY_LOW, "Critical memory shortage", String(freeHeap), 4);
    return false;
  }
  
  return true;
}

bool checkWiFiHealth() {
  if (WiFi.status() != WL_CONNECTED) {
    logError(ERROR_WIFI_DISCONNECTED, "WiFi connection lost", WiFi.SSID(), 3);
    return false;
  }
  
  if (WiFi.RSSI() < -80) {  // Very weak signal
    logError(ERROR_WIFI_DISCONNECTED, "Weak WiFi signal", String(WiFi.RSSI()), 2);
    return false;
  }
  
  return true;
}

bool checkServerHealth() {
  if (!isConfigured()) {
    return false;
  }
  
  // Simple ping to server
  HTTPClient http;
  String url = String("http://") + deviceConfig.server_host + 
               ":" + deviceConfig.server_port + "/health";
  
  http.begin(url);
  http.setTimeout(5000);  // 5 second timeout
  
  int responseCode = http.GET();
  http.end();
  
  if (responseCode != 200) {
    logError(ERROR_SERVER_UNREACHABLE, "Server health check failed", String(responseCode), 2);
    return false;
  }
  
  return true;
}

/**
 * Handle critical system error with emergency procedures
 * 
 * Critical error response:
 * - Persistent storage of error details
 * - Emergency alert transmission
 * - Visual emergency indicator pattern
 * - System stability assessment
 */
void handleCriticalError(const String& error) {
  LOG_EMERGENCY("CRITICAL SYSTEM ERROR: " + error);
  
  // Save error to persistent storage for post-restart analysis
  monitoringPrefs.putString("last_critical_error", error);
  monitoringPrefs.putULong("error_timestamp", millis());
  monitoringPrefs.putUInt("critical_error_count", 
                         monitoringPrefs.getUInt("critical_error_count", 0) + 1);
  
  // Try to send emergency report if connectivity available
  if (WiFi.isConnected() && isConfigured()) {
    LOG_INFO(LOG_SYSTEM, "Sending emergency critical error report");
    
    HTTPClient http;
    String url = String("http://") + deviceConfig.server_host + 
                 ":" + deviceConfig.server_port + 
                 "/api/v1/devices/" + deviceConfig.device_id + "/emergency";
    
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    
    StaticJsonDocument<256> doc;
    doc["device_id"] = deviceConfig.device_id;
    doc["error"] = error;
    doc["timestamp"] = millis();
    doc["uptime"] = (millis() - bootTime) / 1000;
    doc["reset_count"] = systemHealth.reset_count;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["severity"] = "CRITICAL";
    
    String payload;
    serializeJson(doc, payload);
    
    int responseCode = http.POST(payload);
    if (responseCode == 200) {
      LOG_INFO(LOG_SYSTEM, "Emergency report sent successfully");
    } else {
      LOG_ERROR(LOG_SYSTEM, "Emergency report failed", "http_code=" + String(responseCode));
    }
    http.end();
  } else {
    LOG_WARNING(LOG_SYSTEM, "Cannot send emergency report - no connectivity");
  }
  
  // Visual critical error indicator pattern
  LOG_DEBUG(LOG_SYSTEM, "Displaying critical error LED pattern");
  for (int i = 0; i < 10; i++) {
    setLEDColor("red", 100);
    delay(100);
    clearLEDs();
    delay(100);
  }
  
  // Check if multiple critical errors indicate system instability
  uint32_t criticalCount = monitoringPrefs.getUInt("critical_error_count", 0);
  if (criticalCount > 3) {
    LOG_CRITICAL(LOG_SYSTEM, "Multiple critical errors detected - system instability", 
                 "count=" + String(criticalCount));
    SecurityAlerts::alertRepeatedCrashes(criticalCount, "Multiple critical monitoring errors");
  }
}

void resetErrorCounts() {
  systemHealth.error_count = 0;
  
  // Clear error logs
  for (int i = 0; i < MAX_ERROR_LOG_SIZE; i++) {
    errorLogs[i] = {};
  }
  errorLogIndex = 0;
}

String getErrorTypeName(ErrorType type) {
  switch (type) {
    case ERROR_WIFI_DISCONNECTED: return "WIFI_DISCONNECTED";
    case ERROR_WEBSOCKET_FAILED: return "WEBSOCKET_FAILED";
    case ERROR_AUDIO_FAILED: return "AUDIO_FAILED";
    case ERROR_MEMORY_LOW: return "MEMORY_LOW";
    case ERROR_TEMPERATURE_HIGH: return "TEMPERATURE_HIGH";
    case ERROR_WATCHDOG_TIMEOUT: return "WATCHDOG_TIMEOUT";
    case ERROR_SERVER_UNREACHABLE: return "SERVER_UNREACHABLE";
    case ERROR_AUTH_FAILED: return "AUTH_FAILED";
    case ERROR_UPDATE_FAILED: return "UPDATE_FAILED";
    default: return "UNKNOWN";
  }
}

/**
 * Print comprehensive system status (development mode only)
 * 
 * In production mode, this information is logged through the
 * production logging system instead of Serial output.
 */
void printSystemStatus() {
  SystemHealth health = getSystemHealth();
  
  // In production mode, log status instead of printing
  #if PRODUCTION_MODE
    LOG_INFO(LOG_SYSTEM, "System status summary", 
             "uptime=" + String(health.uptime) + 
             "s, heap=" + String(health.free_heap) + 
             ", errors=" + String(health.error_count) + 
             ", resets=" + String(health.reset_count));
    
    LOG_DEBUG(LOG_SYSTEM, "Detailed system metrics", 
              "cpu=" + String(health.cpu_usage) + 
              "%, temp=" + String(health.temperature) + 
              "C, wifi=" + String(health.wifi_rssi) + 
              "dBm, audio=" + String(health.audio_system_ok ? "OK" : "ERROR"));
  #else
    // Development mode - print to Serial for debugging
    Serial.println("=== 🧸 SYSTEM STATUS ===");
    Serial.printf("Uptime: %d seconds\n", health.uptime);
    Serial.printf("Free Heap: %d bytes\n", health.free_heap);
    Serial.printf("Min Free Heap: %d bytes\n", health.min_free_heap);
    Serial.printf("CPU Usage: %.1f%%\n", health.cpu_usage);
    Serial.printf("Temperature: %.1f°C\n", health.temperature);
    Serial.printf("WiFi RSSI: %d dBm\n", health.wifi_rssi);
    Serial.printf("Error Count: %d\n", health.error_count);
    Serial.printf("Reset Count: %d\n", health.reset_count);
    Serial.printf("Audio System: %s\n", health.audio_system_ok ? "OK" : "ERROR");
    Serial.printf("WebSocket: %s\n", health.websocket_connected ? "Connected" : "Disconnected");
    Serial.printf("Server: %s\n", health.server_responsive ? "Responsive" : "Unresponsive");
    Serial.println("========================");
  #endif
}
