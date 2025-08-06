#ifndef SECURITY_ALERTS_H
#define SECURITY_ALERTS_H

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>

// Security Alert System
// Monitors for attacks, failures, and suspicious activity
// Sends automatic alerts to administrators and logs critical events

enum AlertType {
  ALERT_ATTACK_ATTEMPT = 1,
  ALERT_FIRMWARE_TAMPERING = 2,
  ALERT_DATA_LOSS = 3,
  ALERT_SYSTEM_COMPROMISE = 4,
  ALERT_HARDWARE_FAILURE = 5,
  ALERT_NETWORK_INTRUSION = 6,
  ALERT_AUTHENTICATION_FAILURE = 7,
  ALERT_OTA_FAILURE = 8,
  ALERT_MEMORY_EXHAUSTION = 9,
  ALERT_REPEATED_CRASHES = 10
};

enum AlertSeverity {
  SEVERITY_LOW = 1,
  SEVERITY_MEDIUM = 2,
  SEVERITY_HIGH = 3,
  SEVERITY_CRITICAL = 4,
  SEVERITY_EMERGENCY = 5
};

struct SecurityAlert {
  AlertType type;
  AlertSeverity severity;
  String title;
  String description;
  String source;
  unsigned long timestamp;
  String deviceId;
  String evidence;
  bool resolved;
};

struct AttackPattern {
  String pattern;
  int threshold;
  unsigned long timeWindow;
  int currentCount;
  unsigned long windowStart;
};

class SecurityAlerts {
private:
  static Preferences alertPrefs;
  static bool alertingEnabled;
  static String adminEndpoint;
  static String adminEmail;
  static String deviceId;
  static unsigned long lastHeartbeat;
  static int consecutiveFailures;
  
  // Attack pattern detection
  static AttackPattern attackPatterns[];
  static int attackPatternCount;
  
  // Rate limiting for alerts
  static unsigned long lastAlertSent[11]; // Index by AlertType
  static const unsigned long ALERT_COOLDOWN = 300000; // 5 minutes
  
  static bool sendAlert(const SecurityAlert& alert);
  static bool sendToServer(const SecurityAlert& alert);
  static bool sendEmail(const SecurityAlert& alert);
  static void logAlert(const SecurityAlert& alert);
  static void triggerVisualAlert(AlertSeverity severity);
  static void triggerAudioAlert(AlertSeverity severity);
  static String formatAlertMessage(const SecurityAlert& alert);
  static String getAlertTypeName(AlertType type);
  static String getSeverityName(AlertSeverity severity);
  static bool isAlertRateLimited(AlertType type);

public:
  // Initialize security alert system
  static bool init();
  
  // Configure alerting
  static void setAdminEndpoint(const String& endpoint);
  static void setAdminEmail(const String& email);
  static void enableAlerting(bool enable);
  
  // Main alert functions
  static void alertAttackAttempt(const String& attackType, const String& source, const String& evidence = "");
  static void alertFirmwareTampering(const String& details, const String& evidence = "");
  static void alertDataLoss(const String& component, const String& details);
  static void alertSystemCompromise(const String& indicator, const String& evidence);
  static void alertHardwareFailure(const String& component, const String& error);
  static void alertNetworkIntrusion(const String& source, const String& details);
  static void alertAuthenticationFailure(const String& attempt, int count);
  static void alertOTAFailure(const String& version, const String& error);
  static void alertMemoryExhaustion(size_t freeHeap, size_t minHeap);
  static void alertRepeatedCrashes(int crashCount, const String& reason);
  
  // Generic alert function
  static void sendAlert(AlertType type, AlertSeverity severity, const String& title, 
                       const String& description, const String& source = "", 
                       const String& evidence = "");
  
  // Attack pattern detection
  static void detectAttackPatterns(const String& event, const String& source);
  static void updateAttackPattern(const String& pattern);
  static bool isUnderAttack();
  
  // Monitoring functions
  static void monitorSystemHealth();
  static void checkForAnomalies();
  static void sendHeartbeat();
  
  // Alert management
  static void acknowledgeAlert(AlertType type);
  static void resolveAlert(AlertType type);
  static int getPendingAlertCount();
  static void clearOldAlerts();
  
  // Emergency functions
  static void triggerEmergencyMode(const String& reason);
  static void sendEmergencyAlert(const String& message);
  static void activateLockdown();
  
  // Statistics
  static int getAlertCount(AlertType type);
  static unsigned long getLastAlertTime(AlertType type);
  static void resetAlertCounters();
  
  // Testing functions (development only)
  #if !PRODUCTION_MODE
  static void testAlert(AlertType type);
  static void simulateAttack(const String& attackType);
  #endif
};

// Convenience macros for common alerts
#define ALERT_ATTACK(type, source, evidence) SecurityAlerts::alertAttackAttempt(type, source, evidence)
#define ALERT_CRITICAL(title, desc, evidence) SecurityAlerts::sendAlert(ALERT_SYSTEM_COMPROMISE, SEVERITY_CRITICAL, title, desc, "", evidence)
#define ALERT_EMERGENCY(message) SecurityAlerts::sendEmergencyAlert(message)

// Pattern detection macros
#define DETECT_PATTERN(event, source) SecurityAlerts::detectAttackPatterns(event, source)

#endif