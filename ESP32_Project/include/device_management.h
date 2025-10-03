#ifndef DEVICE_MANAGEMENT_H
#define DEVICE_MANAGEMENT_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <WebSocketsServer.h>

// Device management commands
enum DeviceCommand {
  CMD_RESTART,
  CMD_FACTORY_RESET,
  CMD_UPDATE_CONFIG,
  CMD_UPDATE_FIRMWARE,
  CMD_RUN_DIAGNOSTICS,
  CMD_CALIBRATE_AUDIO,
  CMD_SET_LED_TEST,
  CMD_BACKUP_CONFIG,
  CMD_RESTORE_CONFIG,
  CMD_UNKNOWN
};

// Device status
enum DeviceStatus {
  STATUS_IDLE,
  STATUS_BUSY,
  STATUS_UPDATING,
  STATUS_ERROR,
  STATUS_MAINTENANCE
};

// Management configuration
struct ManagementConfig {
  bool remote_management_enabled;
  bool auto_update_enabled;
  bool diagnostics_enabled;
  String management_server;
  int management_port;
  unsigned long last_checkin;
  unsigned long checkin_interval;
};

// Device info structure
struct DeviceInfo {
  String device_id;
  String firmware_version;
  String hardware_version;
  String mac_address;
  String ip_address;
  unsigned long uptime;
  unsigned long last_restart;
  int restart_count;
  DeviceStatus status;
};

// Management functions
bool initDeviceManagement();
void handleDeviceManagement();
bool executeCommand(DeviceCommand cmd, const String& params = "");
bool registerDevice();
bool reportDeviceStatus();
bool checkForUpdates();
void processRemoteCommand(const String& command, const String& params);

// Configuration management
bool updateDeviceConfig(const String& configJson);
bool backupConfiguration();
bool restoreConfiguration(const String& backupData);
bool validateConfiguration(const String& configJson);

// Enhanced configuration backup/restore
bool createFullSystemBackup();
bool restoreFullSystemBackup(const String& backupData);
String getBackupList();

// Diagnostics
bool runDiagnostics();
bool runAudioDiagnostics();
bool runNetworkDiagnostics();
bool runMemoryDiagnostics();
String generateDiagnosticsReport();
String generateComprehensiveDiagnosticReport();
bool runAdvancedMemoryTest();
void generateHealthRecommendations(JsonArray& recommendations);

// Device information
DeviceInfo getDeviceInfo();
String getDeviceFingerprint();
bool updateDeviceInfo();

// Management web interface
void startManagementServer();
void stopManagementServer();
void handleManagementWeb();

// Remote management
void enableRemoteManagement();
void disableRemoteManagement();
bool isRemoteManagementEnabled();

// Command parsing
DeviceCommand parseCommand(const String& commandStr);
String commandToString(DeviceCommand cmd);

// Status management
void setDeviceStatus(DeviceStatus status);
DeviceStatus getDeviceStatus();
void updateStatusLED();

// Remote debugging capabilities
bool initRemoteDebugging();
void handleRemoteDebugging();
void handleDebugWebSocketEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length);
void handleRemoteDebugCommand(uint8_t clientNum, const String& command);
void sendDebugResponse(uint8_t clientNum, const String& type, const String& message);
void sendSystemInfo(uint8_t clientNum);
void sendMemoryMap(uint8_t clientNum);
void sendTaskList(uint8_t clientNum);
void sendPerformanceMetrics(uint8_t clientNum);
void sendRecentLogs(uint8_t clientNum, int lines);
void debugLog(const String& level, const String& message);

// System performance tuning
void initPerformanceProfiles();
bool loadPerformanceProfile(const String& profileName);
void applyPerformanceProfile();
bool setPerformanceProfile(const String& profileName);
float getCurrentCPUUsage();
void updateDiagnosticMetrics();

// Constants
extern const unsigned long DEFAULT_CHECKIN_INTERVAL;
extern const int MANAGEMENT_WEB_PORT;
extern const int DEBUG_WEBSOCKET_PORT;
extern const int DEVICE_MAX_CONFIG_SIZE;
extern const int DIAGNOSTICS_TIMEOUT;
extern const int MAX_DEBUG_CLIENTS;
extern const int PERFORMANCE_SAMPLE_SIZE;

// Global variables
extern ManagementConfig managementConfig;
extern DeviceInfo deviceInfo;
extern DeviceStatus currentStatus;
extern WebServer* managementServer;
extern WebSocketsServer* debugWebSocket;

#endif // DEVICE_MANAGEMENT_H
