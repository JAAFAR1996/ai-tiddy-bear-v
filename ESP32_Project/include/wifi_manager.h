#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <WiFi.h>
#include <WiFiManager.h>
#include <EEPROM.h>
#include <ArduinoJson.h>

// WiFi Manager Configuration
#define WIFI_CONFIG_TIMEOUT 300  // 5 minutes
#define WIFI_AP_NAME "TeddyBear_Setup"
// WiFi AP password will be generated at runtime
extern String wifiAPPassword;
#define EEPROM_SIZE 512

// Configuration Storage Addresses
#define EEPROM_WIFI_CONFIGURED 0
#define EEPROM_SERVER_HOST 10
#define EEPROM_SERVER_PORT 110
#define EEPROM_DEVICE_ID 120
#define EEPROM_DEVICE_SECRET 180

struct DeviceConfig {
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
bool connectToWiFi();
void resetWiFiSettings();
bool saveDeviceConfig(const DeviceConfig& config);
DeviceConfig loadDeviceConfig();
void startConfigPortal();
bool isConfigured();
void handleConfigPortal();
String getDeviceInfo();
void saveConfigCallback();

// Enhanced WiFi management functions
bool testInternetConnection();
void startConnectionMonitoring();
void playVoiceInstruction(const String& instruction);
void startSetupModeMonitoring();
void generateWiFiAPPassword();
void generateDeviceSecretKey();
void handleInternetDisconnection();
void handleSetupMode();
void enterWaitingMode();
void checkPowerButtonLongPress();

// Animation functions
void playSetupAnimation();
void playSuccessAnimation();
void playErrorAnimation();
void playResetAnimation();
void playTimeoutAnimation();

// Global config instance
extern DeviceConfig deviceConfig;
extern WiFiManager wifiManager;

// Global monitoring variables
extern bool isConnectedToInternet;
extern unsigned long lastInternetCheck;
extern unsigned long lastDisconnectionAlert;
extern bool setupModeActive;
extern unsigned long setupModeStartTime;

#endif
