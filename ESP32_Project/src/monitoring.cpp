#include "monitoring.h"
#include "hardware.h"
#include "wifi_manager.h"
#include "websocket_handler.h"
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

bool initMonitoring() {
  Serial.println("📊 Initializing monitoring system...");
  
  // Initialize preferences for persistent data
  monitoringPrefs.begin("monitoring", false);
  
  // Load reset count
  uint32_t resetCount = monitoringPrefs.getUInt("reset_count", 0);
  monitoringPrefs.putUInt("reset_count", resetCount + 1);
  
  // Initialize system health
  systemHealth = {};
  systemHealth.reset_count = resetCount + 1;
  bootTime = millis();
  
  // Initialize watchdog
  initWatchdog();
  
  // Reset error logs
  for (int i = 0; i < MAX_ERROR_LOG_SIZE; i++) {
    errorLogs[i] = {};
  }
  
  Serial.printf("✅ Monitoring initialized. Reset count: %d\n", systemHealth.reset_count);
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

void logError(ErrorType type, const String& message, const String& context, int severity) {
  Serial.printf("🚨 ERROR [%s]: %s\n", getErrorTypeName(type).c_str(), message.c_str());
  
  // Add to error log
  ErrorLog& log = errorLogs[errorLogIndex];
  log.timestamp = millis();
  log.type = type;
  log.message = message;
  log.context = context;
  log.severity = severity;
  
  errorLogIndex = (errorLogIndex + 1) % MAX_ERROR_LOG_SIZE;
  systemHealth.error_count++;
  
  // Show error on LEDs based on severity
  switch (severity) {
    case 1: // Info - Blue
      setLEDColor("blue", 30);
      delay(200);
      clearLEDs();
      break;
    case 2: // Warning - Yellow
      setLEDColor("yellow", 50);
      delay(500);
      clearLEDs();
      break;
    case 3: // Error - Orange
      setLEDColor("orange", 70);
      delay(1000);
      clearLEDs();
      break;
    case 4: // Critical - Red
      for (int i = 0; i < 3; i++) {
        setLEDColor("red", 100);
        delay(300);
        clearLEDs();
        delay(300);
      }
      break;
  }
  
  // Handle critical errors
  if (severity >= 4) {
    handleCriticalError(message);
  }
}

void sendErrorReport() {
  if (!isConfigured() || !WiFi.isConnected()) {
    return;
  }
  
  Serial.println("📤 Sending error report...");
  
  HTTPClient http;
  String url = String("http://") + deviceConfig.server_host + 
               ":" + deviceConfig.server_port + 
               "/api/v1/devices/" + deviceConfig.device_id + "/errors";
  
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + String(deviceConfig.device_secret));
  
  // Create error report
  StaticJsonDocument<2048> doc;
  doc["device_id"] = deviceConfig.device_id;
  doc["timestamp"] = millis();
  doc["error_count"] = systemHealth.error_count;
  
  JsonArray errors = doc.createNestedArray("errors");
  
  // Add recent errors
  for (int i = 0; i < MAX_ERROR_LOG_SIZE; i++) {
    int idx = (errorLogIndex + i) % MAX_ERROR_LOG_SIZE;
    if (errorLogs[idx].timestamp > 0) {
      JsonObject error = errors.createNestedObject();
      error["timestamp"] = errorLogs[idx].timestamp;
      error["type"] = getErrorTypeName(errorLogs[idx].type);
      error["message"] = errorLogs[idx].message;
      error["context"] = errorLogs[idx].context;
      error["severity"] = errorLogs[idx].severity;
    }
  }
  
  String payload;
  serializeJson(doc, payload);
  
  int responseCode = http.POST(payload);
  if (responseCode == 200) {
    Serial.println("✅ Error report sent successfully");
    resetErrorCounts();
  } else {
    Serial.printf("❌ Failed to send error report: %d\n", responseCode);
  }
  
  http.end();
}

void sendHealthReport() {
  if (!isConfigured() || !WiFi.isConnected()) {
    return;
  }
  
  Serial.println("📊 Sending health report...");
  
  HTTPClient http;
  String url = String("http://") + deviceConfig.server_host + 
               ":" + deviceConfig.server_port + 
               "/api/v1/devices/" + deviceConfig.device_id + "/health";
  
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + String(deviceConfig.device_secret));
  
  // Get current health
  SystemHealth health = getSystemHealth();
  
  // Create health report
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
  
  String payload;
  serializeJson(doc, payload);
  
  int responseCode = http.POST(payload);
  if (responseCode == 200) {
    Serial.println("✅ Health report sent successfully");
    systemHealth.server_responsive = true;
  } else {
    Serial.printf("❌ Failed to send health report: %d\n", responseCode);
    systemHealth.server_responsive = false;
    logError(ERROR_SERVER_UNREACHABLE, "Health report failed", String(responseCode), 2);
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

void initWatchdog() {
  Serial.println("🐕 Initializing watchdog timer...");
  
  // Configure watchdog timer
  esp_task_wdt_init(WATCHDOG_TIMEOUT, true);
  esp_task_wdt_add(NULL);  // Add current task to watchdog
  
  Serial.printf("✅ Watchdog initialized with %d second timeout\n", WATCHDOG_TIMEOUT);
}

void feedWatchdog() {
  esp_task_wdt_reset();
}

void handleWatchdogTimeout() {
  Serial.println("🚨 WATCHDOG TIMEOUT - SYSTEM RESTART");
  logError(ERROR_WATCHDOG_TIMEOUT, "System became unresponsive", "", 4);
  delay(1000);
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

void handleCriticalError(const String& error) {
  Serial.printf("🚨 CRITICAL ERROR: %s\n", error.c_str());
  
  // Save error to persistent storage
  monitoringPrefs.putString("last_critical_error", error);
  monitoringPrefs.putULong("error_timestamp", millis());
  
  // Try to send emergency report
  if (WiFi.isConnected() && isConfigured()) {
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
    
    String payload;
    serializeJson(doc, payload);
    
    http.POST(payload);
    http.end();
  }
  
  // Show critical error pattern
  for (int i = 0; i < 10; i++) {
    setLEDColor("red", 100);
    delay(100);
    clearLEDs();
    delay(100);
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

void printSystemStatus() {
  SystemHealth health = getSystemHealth();
  
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
}
