#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <WiFi.h>
#include <EEPROM.h>
#include <ArduinoJson.h>

// WiFi Manager Configuration
#define WIFI_CONFIG_TIMEOUT 300  // 5 minutes
#define WIFI_AP_NAME "TeddyBear_Setup"
#define WIFI_AP_PASSWORD "teddy123"
#define EEPROM_SIZE 512

// Configuration Storage Addresses
#define EEPROM_WIFI_CONFIGURED 0
#define EEPROM_SERVER_HOST 10
#define EEPROM_SERVER_PORT 110
#define EEPROM_DEVICE_ID 120
#define EEPROM_DEVICE_SECRET 180

struct DeviceConfig {
  char wifi_ssid[32];
  char wifi_password[64];
  char server_host[64];
  int server_port;
  char device_id[32];
  char device_secret[64];
  char child_id[32];
  char child_name[32];
  int child_age;
  bool ssl_enabled;
  bool configured;
};

// Function declarations
bool initWiFiManager();
bool initWiFi();  // Combined initialization and connection with internet test
bool connectToWiFi();
bool reconnectWiFi();
void handleWiFiManager();
bool saveDeviceConfig(const DeviceConfig& config);
DeviceConfig loadDeviceConfig();
void startConfigPortal();
bool isConfigured();
String getWiFiDeviceInfo();

// Enhanced WiFi management functions
bool testInternetConnection();
void handleInternetDisconnection();
void handleSetupMode();

// WiFi Quality Monitoring Functions
void initializeWiFiMonitoring();
void monitorWiFiQuality();
void updateWiFiSignalMetrics();
void assessWiFiQuality();
String getRSSIQualityText(int rssi);
void printInitialWiFiStats();

// Smart Reconnection Functions
void resetReconnectionStrategy();
void updateWiFiQualityOnFailure();

// Enhanced WiFi Diagnostics
void printWiFiDiagnostics();

// Global config instance
extern DeviceConfig deviceConfig;

// Global monitoring variables
extern bool isConnectedToInternet;
extern unsigned long lastInternetCheck;

#endif
