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
#define MONITORING_WATCHDOG_TIMEOUT 30  // 30 seconds
#define MEMORY_LEAK_CHECK_INTERVAL 10000  // 10 seconds
#define PERFORMANCE_SAMPLE_INTERVAL 5000   // 5 seconds
#define AUDIO_LATENCY_SAMPLES 20       // Number of latency samples to track

// Memory leak detection
struct MemoryStats {
  uint32_t heap_at_boot;
  uint32_t min_heap_ever;
  uint32_t heap_trend[10];  // Last 10 readings for trend analysis
  int trend_index;
  bool leak_detected;
  float leak_rate;  // bytes per minute
};

// Performance metrics
struct PerformanceMetrics {
  float avg_cpu_usage;
  uint32_t max_loop_time;
  uint32_t avg_loop_time;
  uint32_t wifi_reconnects;
  uint32_t websocket_reconnects;
  uint32_t total_requests;
  uint32_t failed_requests;
  float request_success_rate;
};

// Audio latency tracking
struct AudioLatencyMetrics {
  uint32_t samples[AUDIO_LATENCY_SAMPLES];
  int sample_index;
  uint32_t avg_latency;
  uint32_t max_latency;
  uint32_t min_latency;
  bool latency_warning;
};

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
  MemoryStats memory_stats;
  PerformanceMetrics performance;
  AudioLatencyMetrics audio_latency;
};

// Error types
enum ErrorType {
  ERROR_NONE,
  ERROR_WIFI_DISCONNECTED,
  ERROR_WEBSOCKET_FAILED,
  ERROR_AUDIO_FAILED,
  ERROR_MEMORY_LOW,
  ERROR_TEMPERATURE_HIGH,
  ERROR_WATCHDOG_TIMEOUT,
  ERROR_SERVER_UNREACHABLE,
  ERROR_AUTH_FAILED,
  ERROR_UPDATE_FAILED,
  ERROR_SYSTEM_CHECK_FAILED
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

// Memory leak detection functions
void initMemoryLeakDetection();
void checkMemoryLeak();
bool detectMemoryLeak();
void updateMemoryTrend(uint32_t current_heap);

// Performance monitoring functions
void initPerformanceMetrics();
void updatePerformanceMetrics(uint32_t loop_time);
void recordRequest(bool success);
void recordWiFiReconnect();
void recordWebSocketReconnect();

// Audio latency monitoring functions
void initAudioLatencyTracking();
void recordAudioLatency(uint32_t latency_ms);
void updateAudioLatencyStats();
bool checkAudioLatencyHealth();

// Dashboard functions
void sendDashboardData();
String generateHealthDashboard();

// Global variables
extern SystemHealth systemHealth;
extern ErrorLog errorLogs[MAX_ERROR_LOG_SIZE];
extern int errorLogIndex;
extern unsigned long lastMonitoringReport;
extern unsigned long lastErrorReport;
extern unsigned long lastHealthCheck;
extern unsigned long bootTime;
extern unsigned long lastMemoryLeakCheck;
extern unsigned long lastPerformanceUpdate;
extern unsigned long loopStartTime;

#endif
