#ifndef DEVICE_MANAGEMENT_H
#define DEVICE_MANAGEMENT_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WebServer.h>

// Device management commands
enum DeviceCommand {
  CMD_RESTART,
  CMD_FACTORY_RESET,
  CMD_UPDATE_CONFIG,
  CMD_UPDATE_FIRMWARE,
  CMD_RUN_DIAGNOSTICS,
  CMD_CALIBRATE_AUDIO,
  CMD_CALIBRATE_MOTION,
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

// Diagnostics
bool runDiagnostics();
bool runAudioDiagnostics();
bool runMotionDiagnostics();
bool runNetworkDiagnostics();
bool runMemoryDiagnostics();
String generateDiagnosticsReport();

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

// Constants
extern const unsigned long DEFAULT_CHECKIN_INTERVAL;
extern const int MANAGEMENT_WEB_PORT;
extern const int MAX_CONFIG_SIZE;
extern const int DIAGNOSTICS_TIMEOUT;

// Global variables
extern ManagementConfig managementConfig;
extern DeviceInfo deviceInfo;
extern DeviceStatus currentStatus;
extern WebServer* managementServer;

#endif // DEVICE_MANAGEMENT_H
