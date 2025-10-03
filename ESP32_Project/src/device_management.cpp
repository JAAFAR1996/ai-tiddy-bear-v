#include "device_management.h"
#include "config.h"
#include "jwt_manager.h"
#include "resource_manager.h"
#include <WiFi.h>
#include <ArduinoJson.h>

// 🧸 EMERGENCY SIMPLIFICATION - Audio-only teddy bear management
// Reduced from 1750 lines to minimal essentials for stability

// Simple device state
static bool deviceInitialized = false;
static String deviceMAC = "";
static String deviceIdNormalized = "";
static unsigned long lastHeartbeat = 0;

// Basic device initialization
bool initDeviceManagement() {
  if (deviceInitialized) return true;
  
  Serial.println("🧸 Simple device management init");
  deviceMAC = WiFi.macAddress();
  // Normalize device ID for server compatibility (no colons, lowercase, prefixed)
  {
    String mac = deviceMAC;
    mac.toLowerCase();
    mac.replace(":", "");
    deviceIdNormalized = String("teddy-esp32-") + mac; // matches server auto-registration pattern
    Serial.printf("🔖 Normalized Device ID: %s\n", deviceIdNormalized.c_str());
  }
  deviceInitialized = true;
  
  return true;
}

// Simple device info  
DeviceInfo getDeviceInfo() {
  DeviceInfo info = {};
  info.device_id = deviceIdNormalized;
  return info;
}

String getDeviceInfoJson() {
  DynamicJsonDocument doc(512);
  doc["device_id"] = deviceIdNormalized;
  doc["firmware"] = FIRMWARE_VERSION;
  doc["type"] = "audio_teddy_bear";
  doc["memory_free"] = ESP.getFreeHeap();
  
  String result;
  serializeJson(doc, result);
  return result;
}

// Handle basic device management  
void handleDeviceManagement() {
  if (!deviceInitialized) return;
  
  // Simple periodic tasks only
  if (millis() - lastHeartbeat > 30000) {
    Serial.println("💓 Device management heartbeat");
    lastHeartbeat = millis();
  }
}

// NOTE: isAuthenticated() and authenticateDevice() are in security.cpp
// NOTE: sendHeartbeat() is in websocket_handler.cpp

// Memory cleanup
void cleanupDeviceManagement() {
  deviceInitialized = false;
  Serial.println("🧹 Device management cleanup");
}

// Stub functions for compatibility
void handleRemoteDebugCommand(uint8_t command, const String& data) { /* Simplified */ }
void sendSystemInfo(uint8_t infoLevel) { /* Simplified */ }
void updateDiagnosticMetrics() { /* Simplified */ }
void printSystemStatus() {
  Serial.println("🧸 Teddy bear system: SIMPLE & STABLE");
  Serial.printf("Free memory: %d bytes\n", ESP.getFreeHeap());
}

// Simple device ID
String getDeviceId() {
  return deviceIdNormalized;
}

String getCurrentDeviceId() {
  return deviceIdNormalized; // Normalized for claim/HMAC and WebSocket
}
