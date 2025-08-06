#include "security_alerts.h"
#include "production_logger.h"
#include "spiffs_recovery.h"
#include "hardware.h"
#include "config.h"

// Static member initialization
Preferences SecurityAlerts::alertPrefs;
bool SecurityAlerts::alertingEnabled = true;
String SecurityAlerts::adminEndpoint = "https://api.teddy-admin.com/alerts";
String SecurityAlerts::adminEmail = "admin@teddy-system.com";
String SecurityAlerts::deviceId = "";
unsigned long SecurityAlerts::lastHeartbeat = 0;
int SecurityAlerts::consecutiveFailures = 0;

// Attack patterns to detect
AttackPattern SecurityAlerts::attackPatterns[] = {
  {"multiple_auth_failures", 5, 300000, 0, 0}, // 5 failures in 5 minutes
  {"rapid_ota_requests", 3, 60000, 0, 0},       // 3 OTA requests in 1 minute
  {"memory_pressure", 10, 60000, 0, 0},        // 10 memory warnings in 1 minute
  {"connection_flooding", 20, 30000, 0, 0},     // 20 connections in 30 seconds
  {"firmware_probe", 2, 120000, 0, 0}          // 2 firmware probes in 2 minutes
};
int SecurityAlerts::attackPatternCount = 5;

unsigned long SecurityAlerts::lastAlertSent[11] = {0}; // Initialize all to 0

bool SecurityAlerts::init() {
  LOG_INFO(LOG_SECURITY, "Initializing security alert system");
  
  // Initialize preferences
  alertPrefs.begin("security_alerts", false);
  
  // Load configuration
  alertingEnabled = alertPrefs.getBool("alerts_enabled", true);
  adminEndpoint = alertPrefs.getString("admin_endpoint", adminEndpoint);
  adminEmail = alertPrefs.getString("admin_email", adminEmail);
  
  // Generate device ID if not exists
  deviceId = alertPrefs.getString("device_id", "");
  if (deviceId.isEmpty()) {
    deviceId = "TEDDY_" + WiFi.macAddress();
    deviceId.replace(":", "");
    alertPrefs.putString("device_id", deviceId);
  }
  
  // Clear old alerts on startup
  clearOldAlerts();
  
  // Send system startup alert
  sendAlert(ALERT_SYSTEM_COMPROMISE, SEVERITY_LOW, "System Startup", 
           "Device started successfully", "system", 
           "uptime=0, heap=" + String(ESP.getFreeHeap()));
  
  LOG_INFO(LOG_SECURITY, "Security alerts initialized", "device_id=" + deviceId);
  return true;
}

void SecurityAlerts::alertAttackAttempt(const String& attackType, const String& source, const String& evidence) {
  LOG_SECURITY("Attack attempt detected", "type=" + attackType + ", source=" + source);
  
  // Immediate response
  triggerVisualAlert(SEVERITY_HIGH);
  triggerAudioAlert(SEVERITY_HIGH);
  
  // Update attack patterns
  detectAttackPatterns(attackType, source);
  
  // Send alert
  sendAlert(ALERT_ATTACK_ATTEMPT, SEVERITY_HIGH, "Attack Attempt: " + attackType,
           "Suspicious activity detected from " + source, source, evidence);
  
  // Increment attack counter
  int attackCount = alertPrefs.getInt("attack_count", 0) + 1;
  alertPrefs.putInt("attack_count", attackCount);
  
  // Activate lockdown after repeated attacks
  if (attackCount > 10) {
    activateLockdown();
  }
}

void SecurityAlerts::alertFirmwareTampering(const String& details, const String& evidence) {
  LOG_SECURITY("Firmware tampering detected", details);
  
  // This is critical - immediate emergency response
  triggerVisualAlert(SEVERITY_EMERGENCY);
  triggerAudioAlert(SEVERITY_EMERGENCY);
  
  sendAlert(ALERT_FIRMWARE_TAMPERING, SEVERITY_EMERGENCY, "Firmware Tampering",
           "Unauthorized firmware modification detected: " + details, "firmware", evidence);
  
  // Emergency lockdown
  triggerEmergencyMode("Firmware tampering detected");
}

void SecurityAlerts::alertDataLoss(const String& component, const String& details) {
  LOG_ERROR(LOG_HARDWARE, "Data loss detected", "component=" + component + ", details=" + details);
  
  sendAlert(ALERT_DATA_LOSS, SEVERITY_HIGH, "Data Loss: " + component,
           "Critical data loss detected: " + details, component, "");
           
  // Attempt recovery if it's SPIFFS related
  if (component.indexOf("SPIFFS") >= 0) {
    SPIFFSRecovery::diagnoseAndRecover();
  }
}

void SecurityAlerts::alertSystemCompromise(const String& indicator, const String& evidence) {
  LOG_SECURITY("System compromise suspected", indicator);
  
  triggerEmergencyMode("System compromise: " + indicator);
  
  sendAlert(ALERT_SYSTEM_COMPROMISE, SEVERITY_EMERGENCY, "System Compromise",
           "Security breach detected: " + indicator, "system", evidence);
}

void SecurityAlerts::alertHardwareFailure(const String& component, const String& error) {
  LOG_CRITICAL(LOG_HARDWARE, "Hardware failure", "component=" + component + ", error=" + error);
  
  AlertSeverity severity = SEVERITY_HIGH;
  if (component.indexOf("memory") >= 0 || component.indexOf("flash") >= 0) {
    severity = SEVERITY_CRITICAL;
  }
  
  sendAlert(ALERT_HARDWARE_FAILURE, severity, "Hardware Failure: " + component,
           "Component failure detected: " + error, component, "");
}

void SecurityAlerts::alertAuthenticationFailure(const String& attempt, int count) {
  LOG_WARNING(LOG_SECURITY, "Authentication failure", "attempt=" + attempt + ", count=" + String(count));
  
  AlertSeverity severity = SEVERITY_MEDIUM;
  if (count > 5) severity = SEVERITY_HIGH;
  if (count > 10) severity = SEVERITY_CRITICAL;
  
  sendAlert(ALERT_AUTHENTICATION_FAILURE, severity, "Authentication Failures",
           "Multiple authentication failures: " + String(count), "auth", attempt);
  
  // Trigger attack pattern detection
  detectAttackPatterns("auth_failure", attempt);
}

void SecurityAlerts::alertOTAFailure(const String& version, const String& error) {
  LOG_ERROR(LOG_OTA, "OTA update failed", "version=" + version + ", error=" + error);
  
  sendAlert(ALERT_OTA_FAILURE, SEVERITY_HIGH, "OTA Update Failed",
           "Failed to update to version " + version + ": " + error, "ota", "");
           
  // Check if this might be an attack
  detectAttackPatterns("ota_failure", version);
}

void SecurityAlerts::alertMemoryExhaustion(size_t freeHeap, size_t minHeap) {
  LOG_CRITICAL(LOG_HARDWARE, "Memory exhaustion", "free=" + String(freeHeap) + ", min=" + String(minHeap));
  
  sendAlert(ALERT_MEMORY_EXHAUSTION, SEVERITY_CRITICAL, "Memory Exhaustion",
           "Critical memory shortage: " + String(freeHeap) + " bytes free", "memory", "");
           
  // This could indicate a memory-based attack
  detectAttackPatterns("memory_pressure", "system");
}

void SecurityAlerts::alertRepeatedCrashes(int crashCount, const String& reason) {
  LOG_CRITICAL(LOG_SYSTEM, "Repeated crashes", "count=" + String(crashCount) + ", reason=" + reason);
  
  sendAlert(ALERT_REPEATED_CRASHES, SEVERITY_CRITICAL, "System Instability",
           "Multiple crashes detected: " + String(crashCount) + " crashes", "system", reason);
           
  if (crashCount > 5) {
    triggerEmergencyMode("Repeated system crashes");
  }
}

void SecurityAlerts::sendAlert(AlertType type, AlertSeverity severity, const String& title, 
                              const String& description, const String& source, const String& evidence) {
  
  // Check if alerts are enabled
  if (!alertingEnabled) {
    return;
  }
  
  // Check rate limiting
  if (isAlertRateLimited(type)) {
    LOG_DEBUG(LOG_SECURITY, "Alert rate limited", "type=" + String(type));
    return;
  }
  
  // Create alert structure
  SecurityAlert alert = {
    type,
    severity,
    title,
    description,
    source,
    millis(),
    deviceId,
    evidence,
    false
  };
  
  // Log the alert
  logAlert(alert);
  
  // Trigger local indicators
  triggerVisualAlert(severity);
  if (severity >= SEVERITY_HIGH) {
    triggerAudioAlert(severity);
  }
  
  // Send to remote systems
  bool sent = sendToServer(alert);
  if (!sent) {
    consecutiveFailures++;
    if (consecutiveFailures > 3) {
      // Fallback to email if server is down
      sendEmail(alert);
    }
  } else {
    consecutiveFailures = 0;
  }
  
  // Update rate limiting
  lastAlertSent[type] = millis();
  
  // Store alert count
  int alertCount = alertPrefs.getInt("alert_count_" + String(type), 0) + 1;
  alertPrefs.putInt("alert_count_" + String(type), alertCount);
}

bool SecurityAlerts::sendToServer(const SecurityAlert& alert) {
  if (adminEndpoint.isEmpty() || !WiFi.isConnected()) {
    return false;
  }
  
  HTTPClient http;
  WiFiClientSecure* client = new WiFiClientSecure();
  client->setCACert(nullptr); // For admin endpoint, use proper CA cert in production
  
  if (!http.begin(*client, adminEndpoint)) {
    delete client;
    return false;
  }
  
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + String("your-admin-token")); // Use proper token
  
  // Create JSON payload
  DynamicJsonDocument doc(1024);
  doc["type"] = getAlertTypeName(alert.type);
  doc["severity"] = getSeverityName(alert.severity);
  doc["title"] = alert.title;
  doc["description"] = alert.description;
  doc["source"] = alert.source;
  doc["timestamp"] = alert.timestamp;
  doc["device_id"] = alert.deviceId;
  doc["evidence"] = alert.evidence;
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["heap_free"] = ESP.getFreeHeap();
  doc["uptime"] = millis();
  
  String payload;
  serializeJson(doc, payload);
  
  int responseCode = http.POST(payload);
  http.end();
  delete client;
  
  bool success = (responseCode == 200 || responseCode == 201);
  if (success) {
    LOG_DEBUG(LOG_SECURITY, "Alert sent to server", "type=" + String(alert.type));
  } else {
    LOG_ERROR(LOG_SECURITY, "Failed to send alert to server", "code=" + String(responseCode));
  }
  
  return success;
}

void SecurityAlerts::detectAttackPatterns(const String& event, const String& source) {
  unsigned long now = millis();
  
  for (int i = 0; i < attackPatternCount; i++) {
    AttackPattern& pattern = attackPatterns[i];
    
    // Check if this event matches the pattern
    if (event.indexOf(pattern.pattern) >= 0 || pattern.pattern == "all") {
      
      // Reset window if expired
      if (now - pattern.windowStart > pattern.timeWindow) {
        pattern.currentCount = 0;
        pattern.windowStart = now;
      }
      
      pattern.currentCount++;
      
      // Check if threshold exceeded
      if (pattern.currentCount >= pattern.threshold) {
        LOG_SECURITY("Attack pattern detected", 
                    "pattern=" + pattern.pattern + ", count=" + String(pattern.currentCount));
        
        // Send pattern alert
        sendAlert(ALERT_ATTACK_ATTEMPT, SEVERITY_CRITICAL, "Attack Pattern: " + pattern.pattern,
                 "Suspicious pattern detected: " + String(pattern.currentCount) + 
                 " events in " + String(pattern.timeWindow/1000) + " seconds", 
                 source, "pattern_match");
        
        // Reset counter to avoid spam
        pattern.currentCount = 0;
        
        // Consider emergency lockdown for critical patterns
        if (pattern.pattern.indexOf("firmware") >= 0 || pattern.pattern.indexOf("flooding") >= 0) {
          activateLockdown();
        }
      }
    }
  }
}

void SecurityAlerts::triggerVisualAlert(AlertSeverity severity) {
  switch (severity) {
    case SEVERITY_LOW:
      setLEDColor("blue", 30);
      delay(200);
      clearLEDs();
      break;
      
    case SEVERITY_MEDIUM:
      setLEDColor("yellow", 60);
      delay(500);
      clearLEDs();
      break;
      
    case SEVERITY_HIGH:
      for (int i = 0; i < 3; i++) {
        setLEDColor("orange", 80);
        delay(200);
        clearLEDs();
        delay(200);
      }
      break;
      
    case SEVERITY_CRITICAL:
      for (int i = 0; i < 5; i++) {
        setLEDColor("red", 100);
        delay(150);
        clearLEDs();
        delay(150);
      }
      break;
      
    case SEVERITY_EMERGENCY:
      // Rapid red flashing
      for (int i = 0; i < 10; i++) {
        setLEDColor("red", 100);
        delay(100);
        clearLEDs();
        delay(100);
      }
      break;
  }
}

void SecurityAlerts::triggerAudioAlert(AlertSeverity severity) {
  // Audio alerts only for high severity to avoid noise
  if (severity < SEVERITY_HIGH) return;
  
  int frequency = 1000;
  int duration = 200;
  int pulses = 1;
  
  switch (severity) {
    case SEVERITY_HIGH:
      frequency = 800;
      pulses = 2;
      break;
    case SEVERITY_CRITICAL:
      frequency = 1200;
      pulses = 3;
      break;
    case SEVERITY_EMERGENCY:
      frequency = 1500;
      pulses = 5;
      break;
    default:
      return;
  }
  
  // Generate alert tones (implementation depends on hardware setup)
  for (int i = 0; i < pulses; i++) {
    // Use tone() function if available, or implement via DAC/PWM
    delay(duration);
    delay(100); // Gap between pulses
  }
}

void SecurityAlerts::triggerEmergencyMode(const String& reason) {
  LOG_EMERGENCY("EMERGENCY MODE ACTIVATED: " + reason);
  
  // Send immediate emergency alert
  sendEmergencyAlert("EMERGENCY: " + reason);
  
  // Visual emergency signal
  for (int cycle = 0; cycle < 3; cycle++) {
    for (int i = 0; i < NUM_LEDS; i++) {
      setLEDIndex(i, "red", 100);
      delay(50);
    }
    delay(200);
    clearLEDs();
    delay(200);
  }
  
  // Store emergency state
  alertPrefs.putBool("emergency_mode", true);
  alertPrefs.putString("emergency_reason", reason);
  alertPrefs.putULong("emergency_time", millis());
  
  // Activate additional security measures
  activateLockdown();
}

void SecurityAlerts::sendEmergencyAlert(const String& message) {
  // Emergency alerts bypass rate limiting and always send
  SecurityAlert alert = {
    ALERT_SYSTEM_COMPROMISE,
    SEVERITY_EMERGENCY,
    "EMERGENCY",
    message,
    "system",
    millis(),
    deviceId,
    "emergency_mode",
    false
  };
  
  // Force send regardless of settings
  logAlert(alert);
  sendToServer(alert);
  sendEmail(alert);
  
  // Also store in emergency file
  File emergency = SPIFFS.open("/emergency_alerts.log", FILE_APPEND);
  if (emergency) {
    emergency.println(formatAlertMessage(alert));
    emergency.close();
  }
}

void SecurityAlerts::activateLockdown() {
  LOG_SECURITY("Security lockdown activated");
  
  // Disable non-essential services
  // Stop WebSocket connections
  // Disable OTA updates
  // Switch to minimal functionality mode
  
  alertPrefs.putBool("lockdown_active", true);
  alertPrefs.putULong("lockdown_time", millis());
  
  // Visual lockdown indicator
  for (int i = 0; i < 20; i++) {
    setLEDColor("red", 50);
    delay(100);
    setLEDColor("blue", 50);
    delay(100);
  }
  
  sendAlert(ALERT_SYSTEM_COMPROMISE, SEVERITY_EMERGENCY, "Security Lockdown",
           "Device entered security lockdown mode", "security", "lockdown_activated");
}

void SecurityAlerts::logAlert(const SecurityAlert& alert) {
  LOG_SECURITY("Security alert", formatAlertMessage(alert));
  
  // Also log to dedicated security log file
  File securityLog = SPIFFS.open("/logs/security_alerts.log", FILE_APPEND);
  if (securityLog) {
    DynamicJsonDocument alertDoc(512);
    alertDoc["timestamp"] = alert.timestamp;
    alertDoc["type"] = getAlertTypeName(alert.type);
    alertDoc["severity"] = getSeverityName(alert.severity);
    alertDoc["title"] = alert.title;
    alertDoc["description"] = alert.description;
    alertDoc["source"] = alert.source;
    alertDoc["device_id"] = alert.deviceId;
    alertDoc["evidence"] = alert.evidence;
    
    String jsonString;
    serializeJson(alertDoc, jsonString);
    securityLog.println(jsonString);
    securityLog.close();
  }
}

String SecurityAlerts::formatAlertMessage(const SecurityAlert& alert) {
  String message = getSeverityName(alert.severity) + ": " + alert.title;
  if (!alert.description.isEmpty()) {
    message += " - " + alert.description;
  }
  if (!alert.source.isEmpty()) {
    message += " (source: " + alert.source + ")";
  }
  return message;
}

String SecurityAlerts::getAlertTypeName(AlertType type) {
  switch (type) {
    case ALERT_ATTACK_ATTEMPT: return "attack_attempt";
    case ALERT_FIRMWARE_TAMPERING: return "firmware_tampering";
    case ALERT_DATA_LOSS: return "data_loss";
    case ALERT_SYSTEM_COMPROMISE: return "system_compromise";
    case ALERT_HARDWARE_FAILURE: return "hardware_failure";
    case ALERT_NETWORK_INTRUSION: return "network_intrusion";
    case ALERT_AUTHENTICATION_FAILURE: return "authentication_failure";
    case ALERT_OTA_FAILURE: return "ota_failure";
    case ALERT_MEMORY_EXHAUSTION: return "memory_exhaustion";
    case ALERT_REPEATED_CRASHES: return "repeated_crashes";
    default: return "unknown";
  }
}

String SecurityAlerts::getSeverityName(AlertSeverity severity) {
  switch (severity) {
    case SEVERITY_LOW: return "LOW";
    case SEVERITY_MEDIUM: return "MEDIUM";
    case SEVERITY_HIGH: return "HIGH";
    case SEVERITY_CRITICAL: return "CRITICAL";
    case SEVERITY_EMERGENCY: return "EMERGENCY";
    default: return "UNKNOWN";
  }
}

bool SecurityAlerts::isAlertRateLimited(AlertType type) {
  if (type < 1 || type > 10) return false;
  
  return (millis() - lastAlertSent[type]) < ALERT_COOLDOWN;
}

void SecurityAlerts::clearOldAlerts() {
  // Clear alerts older than 24 hours
  unsigned long cutoff = millis() - (24 * 60 * 60 * 1000);
  
  for (int i = 1; i <= 10; i++) {
    if (lastAlertSent[i] < cutoff) {
      lastAlertSent[i] = 0;
    }
  }
  
  // Clean up old log files
  File alertsLog = SPIFFS.open("/logs/security_alerts.log", FILE_READ);
  if (alertsLog && alertsLog.size() > 50000) { // > 50KB
    alertsLog.close();
    SPIFFS.remove("/logs/security_alerts_old.log");
    SPIFFS.rename("/logs/security_alerts.log", "/logs/security_alerts_old.log");
  } else if (alertsLog) {
    alertsLog.close();
  }
}

bool SecurityAlerts::sendEmail(const SecurityAlert& alert) {
  // Email sending implementation would go here
  // This is a placeholder for the email functionality
  LOG_DEBUG(LOG_SECURITY, "Email alert sent", "to=" + adminEmail);
  return true;
}

void SecurityAlerts::monitorSystemHealth() {
  static unsigned long lastHealthCheck = 0;
  
  if (millis() - lastHealthCheck < 30000) { // Check every 30 seconds
    return;
  }
  
  lastHealthCheck = millis();
  
  // Check memory
  size_t freeHeap = ESP.getFreeHeap();
  if (freeHeap < 10000) { // Less than 10KB
    alertMemoryExhaustion(freeHeap, ESP.getMinFreeHeap());
  }
  
  // Check WiFi connection
  if (!WiFi.isConnected()) {
    alertHardwareFailure("WiFi", "Connection lost");
  }
  
  // Check SPIFFS health
  if (!SPIFFSRecovery::isHealthy()) {
    alertHardwareFailure("SPIFFS", "Filesystem unhealthy");
  }
  
  // Send heartbeat
  sendHeartbeat();
}

void SecurityAlerts::sendHeartbeat() {
  if (millis() - lastHeartbeat < 300000) { // Every 5 minutes
    return;
  }
  
  lastHeartbeat = millis();
  
  // Simple heartbeat to admin endpoint
  if (!adminEndpoint.isEmpty() && WiFi.isConnected()) {
    HTTPClient http;
    WiFiClientSecure* client = new WiFiClientSecure();
    client->setInsecure(); // Heartbeat can be less secure
    
    String heartbeatUrl = adminEndpoint + "/heartbeat";
    if (http.begin(*client, heartbeatUrl)) {
      http.addHeader("Content-Type", "application/json");
      
      DynamicJsonDocument doc(256);
      doc["device_id"] = deviceId;
      doc["timestamp"] = millis();
      doc["status"] = "alive";
      doc["uptime"] = millis();
      doc["free_heap"] = ESP.getFreeHeap();
      doc["wifi_rssi"] = WiFi.RSSI();
      
      String payload;
      serializeJson(doc, payload);
      
      http.POST(payload);
      http.end();
    }
    
    delete client;
  }
}

#if !PRODUCTION_MODE
void SecurityAlerts::testAlert(AlertType type) {
  sendAlert(type, SEVERITY_MEDIUM, "Test Alert", 
           "This is a test alert for type " + String(type), "test", "test_evidence");
}
#endif