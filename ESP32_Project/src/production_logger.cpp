#include "production_logger.h"
#include "config.h"

// Static member initialization
LogLevel ProductionLogger::currentLogLevel = LOG_CRITICAL;
bool ProductionLogger::logToFile = true;
bool ProductionLogger::logToSerial = false; // Disabled in production
String ProductionLogger::logFileName = "/critical_events.log";
int ProductionLogger::maxLogFileSize = 32768; // 32KB max log file
int ProductionLogger::maxLogEntries = 100;
Preferences ProductionLogger::logPrefs;

void ProductionLogger::init() {
  // Initialize preferences for log configuration
  logPrefs.begin("logging", false);
  
  // Set production logging level
  #if PRODUCTION_MODE
    currentLogLevel = LOG_ERROR; // Only errors and critical in production
    logToSerial = false; // No serial output in production
  #else
    currentLogLevel = LOG_DEBUG; // All levels in development
    logToSerial = true; // Serial output in development
  #endif
  
  // Initialize SPIFFS for log file storage
  if (!SPIFFS.begin(true)) {
    // If SPIFFS fails, use emergency logging to serial
    if (logToSerial) {
      Serial.println("EMERGENCY: Failed to initialize SPIFFS for logging");
    }
    logToFile = false;
  }
  
  // Create log directory structure if it doesn't exist
  if (logToFile) {
    File root = SPIFFS.open("/logs");
    if (!root || !root.isDirectory()) {
      SPIFFS.mkdir("/logs");
    }
    logFileName = "/logs/critical.log";
  }
  
  // Log system initialization
  logCritical(LOG_SYSTEM, "Logger initialized", "level=" + String(currentLogLevel));
  
  // Clean up old logs if needed
  rotateLogFile();
}

void ProductionLogger::logCritical(LogCategory category, const String& message, const String& context) {
  if (currentLogLevel < LOG_CRITICAL) return;
  
  LogEntry entry = {
    millis(),
    LOG_CRITICAL,
    category,
    message,
    context
  };
  
  String formattedMessage = formatLogEntry(entry);
  
  // Critical messages always go to available outputs
  if (logToSerial) {
    Serial.println("[CRITICAL] " + formattedMessage);
  }
  
  if (logToFile) {
    writeToFile(entry);
  }
  
  // Flash LED for critical errors
  // Critical events also trigger hardware indicators
}

void ProductionLogger::logError(LogCategory category, const String& message, const String& context) {
  if (currentLogLevel < LOG_ERROR) return;
  
  LogEntry entry = {
    millis(),
    LOG_ERROR,
    category,
    message,
    context
  };
  
  String formattedMessage = formatLogEntry(entry);
  
  if (logToSerial) {
    Serial.println("[ERROR] " + formattedMessage);
  }
  
  if (logToFile) {
    writeToFile(entry);
  }
}

void ProductionLogger::logWarning(LogCategory category, const String& message, const String& context) {
  if (currentLogLevel < LOG_WARNING) return;
  
  LogEntry entry = {
    millis(),
    LOG_WARNING,
    category,
    message,
    context
  };
  
  if (logToSerial) {
    Serial.println("[WARNING] " + formatLogEntry(entry));
  }
  
  // Warnings not logged to file in production to save space
  #if !PRODUCTION_MODE
  if (logToFile) {
    writeToFile(entry);
  }
  #endif
}

void ProductionLogger::logInfo(LogCategory category, const String& message, const String& context) {
  if (currentLogLevel < LOG_INFO) return;
  
  if (logToSerial) {
    LogEntry entry = {millis(), LOG_INFO, category, message, context};
    Serial.println("[INFO] " + formatLogEntry(entry));
  }
  // Info messages not written to file to preserve space for critical events
}

void ProductionLogger::logDebug(LogCategory category, const String& message, const String& context) {
  if (currentLogLevel < LOG_DEBUG) return;
  
  if (logToSerial) {
    LogEntry entry = {millis(), LOG_DEBUG, category, message, context};
    Serial.println("[DEBUG] " + formatLogEntry(entry));
  }
  // Debug messages never written to file
}

void ProductionLogger::logSecurityEvent(const String& event, const String& details) {
  // Security events are ALWAYS logged regardless of log level
  LogEntry entry = {
    millis(),
    LOG_CRITICAL,
    LOG_SECURITY,
    "SECURITY: " + event,
    details
  };
  
  String formattedMessage = formatLogEntry(entry);
  
  // Always output security events
  if (logToSerial) {
    Serial.println("[SECURITY] " + formattedMessage);
  }
  
  if (logToFile) {
    writeToFile(entry);
  }
  
  // Security events also saved to separate file
  File securityLog = SPIFFS.open("/logs/security.log", FILE_APPEND);
  if (securityLog) {
    securityLog.println(formattedMessage);
    securityLog.close();
  }
}

void ProductionLogger::logAttackAttempt(const String& attackType, const String& source) {
  logSecurityEvent("ATTACK_ATTEMPT: " + attackType, "source=" + source);
  
  // Increment attack counter
  int attackCount = logPrefs.getInt("attack_count", 0) + 1;
  logPrefs.putInt("attack_count", attackCount);
  
  // Emergency response for repeated attacks
  if (attackCount > 5) {
    emergencyLog("REPEATED_ATTACKS: " + String(attackCount) + " attempts");
  }
}

void ProductionLogger::logSystemStatus(const String& component, bool healthy, const String& details) {
  LogLevel level = healthy ? LOG_INFO : LOG_ERROR;
  LogCategory category = LOG_SYSTEM;
  
  String status = healthy ? "OK" : "FAILED";
  String message = component + "_STATUS: " + status;
  
  if (level == LOG_ERROR) {
    logError(category, message, details);
  } else if (currentLogLevel >= LOG_INFO) {
    logInfo(category, message, details);
  }
}

void ProductionLogger::setLogLevel(LogLevel level) {
  currentLogLevel = level;
  logPrefs.putInt("log_level", (int)level);
}

void ProductionLogger::enableFileLogging(bool enable) {
  logToFile = enable && SPIFFS.begin();
  logPrefs.putBool("log_to_file", logToFile);
}

void ProductionLogger::enableSerialLogging(bool enable) {
  logToSerial = enable;
  logPrefs.putBool("log_to_serial", logToSerial);
}

void ProductionLogger::emergencyLog(const String& message) {
  // Emergency logs are NEVER filtered and always output
  String timestamp = String(millis());
  String emergencyMessage = "[" + timestamp + "] EMERGENCY: " + message;
  
  // Always try serial first
  Serial.println(emergencyMessage);
  
  // Try to write to emergency file
  File emergency = SPIFFS.open("/emergency.log", FILE_APPEND);
  if (emergency) {
    emergency.println(emergencyMessage);
    emergency.close();
  }
  
  // Also try to write to main log
  File mainLog = SPIFFS.open(logFileName, FILE_APPEND);
  if (mainLog) {
    mainLog.println(emergencyMessage);
    mainLog.close();
  }
}

void ProductionLogger::writeToFile(const LogEntry& entry) {
  if (!logToFile) return;
  
  // Check if log file needs rotation
  if (getLogFileSize() > maxLogFileSize) {
    rotateLogFile();
  }
  
  File logFile = SPIFFS.open(logFileName, FILE_APPEND);
  if (!logFile) {
    // If can't open log file, write to emergency log
    emergencyLog("Failed to open log file: " + entry.message);
    return;
  }
  
  // Write structured log entry
  DynamicJsonDocument logDoc(512);
  logDoc["timestamp"] = entry.timestamp;
  logDoc["level"] = getLevelName(entry.level);
  logDoc["category"] = getCategoryName(entry.category);
  logDoc["message"] = entry.message;
  if (!entry.context.isEmpty()) {
    logDoc["context"] = entry.context;
  }
  logDoc["uptime"] = millis();
  logDoc["free_heap"] = ESP.getFreeHeap();
  
  String jsonString;
  serializeJson(logDoc, jsonString);
  logFile.println(jsonString);
  logFile.close();
}

void ProductionLogger::rotateLogFile() {
  if (!logToFile) return;
  
  // Check file size
  File logFile = SPIFFS.open(logFileName, FILE_READ);
  if (!logFile) return;
  
  size_t fileSize = logFile.size();
  logFile.close();
  
  if (fileSize > maxLogFileSize) {
    // Create backup of current log
    String backupName = "/logs/critical_backup.log";
    SPIFFS.remove(backupName); // Remove old backup
    SPIFFS.rename(logFileName, backupName);
    
    // Start fresh log file
    File newLog = SPIFFS.open(logFileName, FILE_WRITE);
    if (newLog) {
      DynamicJsonDocument rotationDoc(256);
      rotationDoc["timestamp"] = millis();
      rotationDoc["event"] = "log_rotation";
      rotationDoc["old_size"] = fileSize;
      rotationDoc["backup_file"] = backupName;
      
      String rotationEntry;
      serializeJson(rotationDoc, rotationEntry);
      newLog.println(rotationEntry);
      newLog.close();
    }
  }
}

String ProductionLogger::formatLogEntry(const LogEntry& entry) {
  String formatted = "[" + String(entry.timestamp) + "] ";
  formatted += getCategoryName(entry.category) + ": ";
  formatted += entry.message;
  
  if (!entry.context.isEmpty()) {
    formatted += " (" + entry.context + ")";
  }
  
  return formatted;
}

String ProductionLogger::getCategoryName(LogCategory category) {
  switch (category) {
    case LOG_SYSTEM: return "SYSTEM";
    case LOG_SECURITY: return "SECURITY";
    case LOG_OTA: return "OTA";
    case LOG_NETWORK: return "NETWORK";
    case LOG_AUDIO: return "AUDIO";
    case LOG_HARDWARE: return "HARDWARE";
    case LOG_USER: return "USER";
    default: return "UNKNOWN";
  }
}

String ProductionLogger::getLevelName(LogLevel level) {
  switch (level) {
    case LOG_CRITICAL: return "CRITICAL";
    case LOG_ERROR: return "ERROR";
    case LOG_WARNING: return "WARNING";
    case LOG_INFO: return "INFO";
    case LOG_DEBUG: return "DEBUG";
    default: return "UNKNOWN";
  }
}

String ProductionLogger::getLogFilePath() {
  return logFileName;
}

bool ProductionLogger::exportLogs(const String& exportPath) {
  File source = SPIFFS.open(logFileName, FILE_READ);
  File dest = SPIFFS.open(exportPath, FILE_WRITE);
  
  if (!source || !dest) {
    return false;
  }
  
  // Copy log contents
  while (source.available()) {
    dest.write(source.read());
  }
  
  source.close();
  dest.close();
  return true;
}

void ProductionLogger::clearLogs() {
  SPIFFS.remove(logFileName);
  SPIFFS.remove("/logs/critical_backup.log");
  SPIFFS.remove("/logs/security.log");
  SPIFFS.remove("/emergency.log");
  
  logCritical(LOG_SYSTEM, "Logs cleared", "user_action");
}

int ProductionLogger::getLogFileSize() {
  File logFile = SPIFFS.open(logFileName, FILE_READ);
  if (!logFile) return 0;
  
  int size = logFile.size();
  logFile.close();
  return size;
}

int ProductionLogger::getLogEntryCount() {
  File logFile = SPIFFS.open(logFileName, FILE_READ);
  if (!logFile) return 0;
  
  int count = 0;
  while (logFile.available()) {
    String line = logFile.readStringUntil('\n');
    if (line.length() > 0) count++;
  }
  
  logFile.close();
  return count;
}