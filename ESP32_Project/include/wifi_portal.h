#ifndef WIFI_PORTAL_H
#define WIFI_PORTAL_H

#include <Arduino.h>
#include <WiFi.h>

// WiFi Portal Functions
bool startWiFiPortal();
void handleWiFiPortal();
void stopWiFiPortal();
bool isPortalActive();
bool isConfigurationComplete();

// Internal Functions
void setupPortalRoutes();
String generatePortalHTML();
void handlePortalRoot();
void handleNetworkScan();
void handleWiFiConnect();
void handleConnectionStatus();
void handleDeviceConfig();
void handleRestart();
String getEncryptionType(wifi_auth_mode_t encryptionType);

#endif