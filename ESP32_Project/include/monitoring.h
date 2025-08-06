#ifndef MONITORING_H
#define MONITORING_H

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <esp_task_wdt.h>

// Monitoring Configuration
#define MONITORING_INTERVAL 60000      // 1 minute
#define ERROR_REPORT_INTERVAL 300000   // 5 minutes
#define HEALTH_CHECK_INTERVAL 30000    // 30 seconds
#define MAX_ERROR_LOG_SIZE 50
#define WATCHDOG_TIMEOUT 30            // 30 seconds

// System health metrics
struct SystemHealth {
  float cpu_usage;
  uint32_t free_heap;
  uint32_t min_free_heap;
  float temperature;
  int wifi_rssi;
  uint32_t uptime;
  uint32_t error_count;
  uint32_t reset_count;
  bool audio_system_ok;
  bool websocket_connected;
  bool server_responsive;
};

// Error types
enum ErrorType {
  ERROR_WIFI_DISCONNECTED,
  ERROR_WEBSOCKET_FAILED,
  ERROR_AUDIO_FAILED,
  ERROR_MEMORY_LOW,
  ERROR_TEMPERATURE_HIGH,
  ERROR_WATCHDOG_TIMEOUT,
  ERROR_SERVER_UNREACHABLE,
  ERROR_AUTH_FAILED,
  ERROR_UPDATE_FAILED
};

// Error log entry
struct ErrorLog {
  unsigned long timestamp;
  ErrorType type;
  String message;
  String context;
  int severity;  // 1=Info, 2=Warning, 3=Error, 4=Critical
};

// Function declarations
bool initMonitoring();
void handleMonitoring();
SystemHealth getSystemHealth();
void logError(ErrorType type, const String& message, const String& context = "", int severity = 3);
void sendErrorReport();
void sendHealthReport();
bool performHealthCheck();
void initWatchdog();
void feedWatchdog();
void handleWatchdogTimeout();
void resetErrorCounts();
String getErrorTypeName(ErrorType type);
void printSystemStatus();
float getCPUUsage();
float getTemperature();
bool checkMemoryHealth();
bool checkWiFiHealth();
bool checkServerHealth();
void handleCriticalError(const String& error);

// Global variables
extern SystemHealth systemHealth;
extern ErrorLog errorLogs[MAX_ERROR_LOG_SIZE];
extern int errorLogIndex;
extern unsigned long lastMonitoringReport;
extern unsigned long lastErrorReport;
extern unsigned long lastHealthCheck;
extern unsigned long bootTime;

#endif
