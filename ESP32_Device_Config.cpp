/*
 * ESP32 AI Teddy Bear - Device Configuration Implementation
 * =======================================================
 * إدارة إعدادات الجهاز مع NVS storage والتحقق من الوقت
 */

#include "ESP32_Config_Headers.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <esp_crt_bundle.h>
#include <time.h>

class ESP32DeviceConfig {
private:
    Preferences preferences;
    String deviceId;
    String currentHost;
    int currentPort;
    bool timeValidated;
    
public:
    ESP32DeviceConfig() {
        currentHost = DEFAULT_SERVER_HOST;
        currentPort = DEFAULT_SERVER_PORT;
        timeValidated = false;
    }
    
    // ==============================================
    // TIME VALIDATION - يجب أن يتم قبل أي TLS
    // ==============================================
    bool validate_time_before_tls() {
        DEBUG_PRINTLN("[TIME] Validating system time before TLS...");
        
        // Configure NTP
        configTime(0, 0, NTP_SERVER_PRIMARY, NTP_SERVER_SECONDARY);
        
        // Wait for time sync with timeout
        unsigned long startTime = millis();
        while (!time(nullptr) && (millis() - startTime) < NTP_TIMEOUT_MS) {
            delay(100);
            DEBUG_PRINT(".");
        }
        DEBUG_PRINTLN();
        
        time_t now = time(nullptr);
        if (now < 1000000000) { // Basic sanity check (after year 2001)
            DEBUG_PRINTLN("[TIME] ❌ Failed to get valid time from NTP");
            return false;
        }
        
        struct tm timeinfo;
        gmtime_r(&now, &timeinfo);
        
        DEBUG_PRINTF("[TIME] ✅ Current time: %04d-%02d-%02d %02d:%02d:%02d UTC\n",
                    timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
                    timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
        
        timeValidated = true;
        return true;
    }
    
    // ==============================================
    // DEVICE CONFIGURATION MANAGEMENT
    // ==============================================
    bool initializeDevice() {
        preferences.begin("teddy_config", false);
        
        // Load or generate device ID
        deviceId = preferences.getString("device_id", "");
        if (deviceId.isEmpty()) {
            deviceId = generateDeviceId();
            preferences.putString("device_id", deviceId);
            DEBUG_PRINTLN("[CONFIG] ✅ Generated new device ID: " + deviceId);
        } else {
            DEBUG_PRINTLN("[CONFIG] ✅ Loaded device ID: " + deviceId);
        }
        
        // Load saved host configuration
        currentHost = preferences.getString("host", DEFAULT_SERVER_HOST);
        currentPort = preferences.getInt("port", DEFAULT_SERVER_PORT);
        
        // Validate host consistency
        if (!VALIDATE_HOST(currentHost.c_str())) {
            DEBUG_PRINTLN("[CONFIG] ⚠️ Invalid host detected, using default");
            currentHost = DEFAULT_SERVER_HOST;
            preferences.putString("host", currentHost);
        }
        
        return true;
    }
    
    // ==============================================
    // CONFIGURATION FETCHING
    // ==============================================
    bool fetchServerConfig() {
        if (!timeValidated) {
            DEBUG_PRINTLN("[CONFIG] ❌ Time not validated - cannot proceed with TLS");
            return false;
        }
        
        DEBUG_PRINTLN("[CONFIG] Fetching server configuration...");
        
        WiFiClientSecure client;
        HTTPClient https;
        
        // استخدم Mozilla CA bundle - الطريقة الأفضل
        client.setCACertBundle(esp_crt_bundle_attach);
        client.setTimeout(TLS_TIMEOUT_MS);
        
        String configUrl = "https://" + currentHost + CONFIG_UPDATE_ENDPOINT;
        DEBUG_PRINTLN("[CONFIG] Connecting to: " + configUrl);
        
        https.begin(client, configUrl);
        https.addHeader("User-Agent", "ESP32-TeddyBear/" + String(FIRMWARE_VERSION));
        https.setTimeout(HTTP_TIMEOUT_MS);
        
        int httpCode = https.GET();
        
        if (httpCode == HTTP_CODE_OK) {
            String payload = https.getString();
            DEBUG_PRINTLN("[CONFIG] ✅ Received config: " + payload);
            
            if (parseAndSaveConfig(payload)) {
                https.end();
                return true;
            }
        } else {
            DEBUG_PRINTF("[CONFIG] ❌ HTTP error: %d\n", httpCode);
            if (httpCode > 0) {
                String error = https.getString();
                DEBUG_PRINTLN("[CONFIG] Error details: " + error);
            }
        }
        
        https.end();
        return false;
    }
    
    // ==============================================
    // FIRMWARE UPDATE CHECK
    // ==============================================
    bool checkFirmwareUpdate() {
        if (!timeValidated) {
            DEBUG_PRINTLN("[FIRMWARE] ❌ Time not validated - cannot proceed with TLS");
            return false;
        }
        
        DEBUG_PRINTLN("[FIRMWARE] Checking for firmware updates...");
        
        WiFiClientSecure client;
        HTTPClient https;
        
        client.setCACertBundle(esp_crt_bundle_attach);
        client.setTimeout(TLS_TIMEOUT_MS);
        
        String firmwareUrl = "https://" + currentHost + FIRMWARE_UPDATE_ENDPOINT;
        DEBUG_PRINTLN("[FIRMWARE] Connecting to: " + firmwareUrl);
        
        https.begin(client, firmwareUrl);
        https.addHeader("User-Agent", "ESP32-TeddyBear/" + String(FIRMWARE_VERSION));
        https.setTimeout(HTTP_TIMEOUT_MS);
        
        int httpCode = https.GET();
        
        if (httpCode == HTTP_CODE_OK) {
            String payload = https.getString();
            DEBUG_PRINTLN("[FIRMWARE] ✅ Received firmware info: " + payload);
            
            DynamicJsonDocument doc(1024);
            DeserializationError error = deserializeJson(doc, payload);
            
            if (!error) {
                String serverVersion = doc["version"].as<String>();
                String downloadUrl = doc["url"].as<String>();
                
                DEBUG_PRINTLN("[FIRMWARE] Server version: " + serverVersion);
                DEBUG_PRINTLN("[FIRMWARE] Current version: " + String(FIRMWARE_VERSION));
                
                if (serverVersion != String(FIRMWARE_VERSION)) {
                    DEBUG_PRINTLN("[FIRMWARE] 🔄 Update available!");
                    // TODO: Implement OTA update logic
                    return true;
                } else {
                    DEBUG_PRINTLN("[FIRMWARE] ✅ Firmware up to date");
                }
            }
        } else {
            DEBUG_PRINTF("[FIRMWARE] ❌ HTTP error: %d\n", httpCode);
        }
        
        https.end();
        return false;
    }
    
private:
    String generateDeviceId() {
        uint64_t chipId = ESP.getEfuseMac();
        return "ESP32_" + String((uint32_t)(chipId >> 16), HEX);
    }
    
    bool parseAndSaveConfig(const String& jsonConfig) {
        DynamicJsonDocument doc(512);
        DeserializationError error = deserializeJson(doc, jsonConfig);
        
        if (error) {
            DEBUG_PRINTLN("[CONFIG] ❌ JSON parse error: " + String(error.c_str()));
            return false;
        }
        
        // Update configuration from server
        if (doc.containsKey("host")) {
            String newHost = doc["host"].as<String>();
            if (VALIDATE_HOST(newHost.c_str())) {
                currentHost = newHost;
                preferences.putString("host", currentHost);
                DEBUG_PRINTLN("[CONFIG] ✅ Updated host: " + currentHost);
            }
        }
        
        if (doc.containsKey("port")) {
            currentPort = doc["port"].as<int>();
            preferences.putInt("port", currentPort);
            DEBUG_PRINTF("[CONFIG] ✅ Updated port: %d\n", currentPort);
        }
        
        if (doc.containsKey("ws_path")) {
            String wsPath = doc["ws_path"].as<String>();
            preferences.putString("ws_path", wsPath);
            DEBUG_PRINTLN("[CONFIG] ✅ Updated WebSocket path: " + wsPath);
        }
        
        return true;
    }
    
public:
    // Getters
    String getDeviceId() const { return deviceId; }
    String getHost() const { return currentHost; }
    int getPort() const { return currentPort; }
    String getWebSocketURL() const {
        String wsPath = preferences.getString("ws_path", WS_CONNECT_ENDPOINT);
        return "wss://" + currentHost + wsPath;
    }
    bool isTimeValidated() const { return timeValidated; }
};

// Global instance
ESP32DeviceConfig deviceConfig;