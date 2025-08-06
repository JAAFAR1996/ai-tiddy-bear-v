#ifndef PRODUCTION_LOGGER_H
#define PRODUCTION_LOGGER_H

#include <Arduino.h>
#include <SPIFFS.h>
#include <ArduinoJson.h>
#include <Preferences.h>

// Production logging system with configurable levels
// Only critical information is logged in production mode

enum LogLevel {
  LOG_NONE = 0,      // No logging (production)
  LOG_CRITICAL = 1,  // Only critical errors (security, hardware failures)
  LOG_ERROR = 2,     // Errors that affect functionality
  LOG_WARNING = 3,   // Warnings (development/debug)
  LOG_INFO = 4,      // Informational (development only)
  LOG_DEBUG = 5      // Debug information (development only)
};

enum LogCategory {
  LOG_SYSTEM = 0,     // System startup, shutdown, crashes
  LOG_SECURITY = 1,   // Security events, attacks, authentication
  LOG_OTA = 2,        // OTA updates, firmware changes
  LOG_NETWORK = 3,    // WiFi, connectivity issues
  LOG_AUDIO = 4,      // Audio system errors
  LOG_HARDWARE = 5,   // Hardware failures, memory issues
  LOG_USER = 6        // User interactions, safety alerts
};

struct LogEntry {
  unsigned long timestamp;
  LogLevel level;
  LogCategory category;
  String message;
  String context;
};

class ProductionLogger {
private:
  static LogLevel currentLogLevel;
  static bool logToFile;
  static bool logToSerial;
  static String logFileName;
  static int maxLogFileSize;
  static int maxLogEntries;
  static Preferences logPrefs;
  
  static void rotateLogFile();
  static void writeToFile(const LogEntry& entry);
  static String formatLogEntry(const LogEntry& entry);
  static String getCategoryName(LogCategory category);
  static String getLevelName(LogLevel level);

public:
  // Initialize logger with production settings
  static void init();
  
  // Main logging functions - only log if level is enabled
  static void logCritical(LogCategory category, const String& message, const String& context = "");
  static void logError(LogCategory category, const String& message, const String& context = "");
  static void logWarning(LogCategory category, const String& message, const String& context = "");
  static void logInfo(LogCategory category, const String& message, const String& context = "");
  static void logDebug(LogCategory category, const String& message, const String& context = "");
  
  // Security-specific logging (always logged regardless of level)
  static void logSecurityEvent(const String& event, const String& details = "");
  static void logAttackAttempt(const String& attackType, const String& source = "");
  
  // System health logging
  static void logSystemStatus(const String& component, bool healthy, const String& details = "");
  
  // Configuration
  static void setLogLevel(LogLevel level);
  static void enableFileLogging(bool enable);
  static void enableSerialLogging(bool enable);
  
  // Log file management
  static String getLogFilePath();
  static bool exportLogs(const String& exportPath);
  static void clearLogs();
  static void emergencyLog(const String& message); // Always logged, never filtered
  
  // Get log statistics
  static int getLogFileSize();
  static int getLogEntryCount();
};

// Convenience macros for different log levels
#if PRODUCTION_MODE
  // In production: only critical and security events
  #define LOG_CRITICAL(category, message, ...) ProductionLogger::logCritical(category, message, ##__VA_ARGS__)
  #define LOG_ERROR(category, message, ...) ProductionLogger::logError(category, message, ##__VA_ARGS__)
  #define LOG_WARNING(category, message, ...) // Disabled in production
  #define LOG_INFO(category, message, ...) // Disabled in production
  #define LOG_DEBUG(category, message, ...) // Disabled in production
  #define LOG_SECURITY(event, ...) ProductionLogger::logSecurityEvent(event, ##__VA_ARGS__)
#else
  // In development: all levels enabled
  #define LOG_CRITICAL(category, message, ...) ProductionLogger::logCritical(category, message, ##__VA_ARGS__)
  #define LOG_ERROR(category, message, ...) ProductionLogger::logError(category, message, ##__VA_ARGS__)
  #define LOG_WARNING(category, message, ...) ProductionLogger::logWarning(category, message, ##__VA_ARGS__)
  #define LOG_INFO(category, message, ...) ProductionLogger::logInfo(category, message, ##__VA_ARGS__)
  #define LOG_DEBUG(category, message, ...) ProductionLogger::logDebug(category, message, ##__VA_ARGS__)
  #define LOG_SECURITY(event, ...) ProductionLogger::logSecurityEvent(event, ##__VA_ARGS__)
#endif

// Emergency logging - never disabled
#define LOG_EMERGENCY(message) ProductionLogger::emergencyLog(message)

// Compatibility macros to gradually replace Serial.print statements
#if PRODUCTION_MODE
  #define DEBUG_PRINT(x) // Disabled in production
  #define DEBUG_PRINTLN(x) // Disabled in production
  #define DEBUG_PRINTF(format, ...) // Disabled in production
#else
  #define DEBUG_PRINT(x) Serial.print(x)
  #define DEBUG_PRINTLN(x) Serial.println(x)
  #define DEBUG_PRINTF(format, ...) Serial.printf(format, ##__VA_ARGS__)
#endif

#endif