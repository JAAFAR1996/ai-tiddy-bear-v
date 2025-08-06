#ifndef OTA_MANAGER_H
#define OTA_MANAGER_H

#include <ArduinoOTA.h>
#include <AsyncElegantOTA.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <mbedtls/sha256.h>
#include <mbedtls/pk.h>
#include <mbedtls/rsa.h>

// OTA Configuration
#define OTA_PORT 3232
#define OTA_HOSTNAME "AI-TeddyBear"
// OTA password will be generated at runtime
extern String otaPassword;

// RSA Public Key for firmware signature verification
// This key should match your private signing key
const char* FIRMWARE_PUBLIC_KEY = R"EOF(
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwl2lKOm9N6yp7qI8ZKr3
qbLF+XYgqKaL5nH2yG9x8aB3cD5hJ7kL9xP2qS6aY3pN5R7rT8hQ2vW1xE3sA5bZ
6NnR8qP9tV7gH5jK3mO8xY2bF1aS9dE6rN4tQ7hJ8nL5qG9xY7pS6aZ3nF2yB8aQ
3cD5hK7kL9xP2qS6aY3pN5R7rT8hQ2vW1xE3sA5bZ6NnR8qP9tV7gH5jK3mO8xY2
bF1aS9dE6rN4tQ7hJ8nL5qG9xY7pS6aZ3nF2yB8aQ3cD5hK7kL9xP2qS6aY3pN5R
7rT8hQ2vW1xE3sA5bZ6NnR8qP9tV7gH5jK3mO8xY2bF1aS9dE6rN4tQ7hJ8nL5qG
9xY7pS6aZ3nF2yB8aQIDAQAB
-----END PUBLIC KEY-----
)EOF";

// Minimum allowed firmware version (for anti-rollback)
#define MIN_FIRMWARE_VERSION "1.0.0"
#define UPDATE_CHECK_INTERVAL 3600000  // 1 hour
#define WEB_SERVER_PORT 80

// Update server configuration
struct FirmwareInfo {
  String version;
  String download_url;
  String checksum;
  String signature;  // RSA signature
  String release_notes;
  bool force_update;
  size_t file_size;
  String min_version; // For anti-rollback
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
bool verifyFirmwareSignature(const uint8_t* firmwareData, size_t dataSize, const String& signature);
bool isVersionAllowed(const String& newVersion);
int compareVersions(const String& v1, const String& v2);
void generateOTAPassword();
String getCurrentVersion();
void startWebServer();
void handleWebRequests();
FirmwareInfo parseUpdateResponse(const String& response);

// Global instances
extern AsyncWebServer webServer;
extern unsigned long lastUpdateCheck;

#endif
