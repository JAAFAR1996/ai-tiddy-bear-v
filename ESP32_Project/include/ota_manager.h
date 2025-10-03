#ifndef OTA_MANAGER_H
#define OTA_MANAGER_H

#include <ArduinoOTA.h>
#ifndef PRODUCTION_BUILD
#include <ElegantOTA.h>
#endif
#include <WebServer.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <esp_https_ota.h>

// OTA Configuration
#define OTA_PORT 3232
#define OTA_HOSTNAME "AI-TeddyBear"
#define OTA_PASSWORD "teddy-update-2025"
#define UPDATE_CHECK_INTERVAL 3600000  // 1 hour
#define WEB_SERVER_PORT 80

// Update server configuration
struct FirmwareInfo {
  String version;
  String download_url;
  String checksum;
  String release_notes;
  bool force_update;
  size_t file_size;
};

// Function declarations
bool initOTA();
void handleOTA();
bool checkForUpdates();
bool downloadAndInstallUpdate(const String& url);
void onOTAStart();
void onOTAProgress(unsigned int progress, unsigned int total);
void onOTAEnd();
void onOTAError(ota_error_t error);
bool validateFirmware(const String& checksum);
String getCurrentVersion();
void startWebServer();
void handleWebRequests();
FirmwareInfo parseUpdateResponse(const String& response);

#ifdef PRODUCTION_BUILD
bool performSecureOTAUpdate(const String& url);
#endif

// Global instances
extern WebServer webServer;
extern unsigned long lastUpdateCheck;

#endif
