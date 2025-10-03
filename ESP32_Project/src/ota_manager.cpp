#include "ota_manager.h"
#ifdef ENABLE_ELEGANT_OTA
#include <ElegantOTA.h>
#endif
#include "hardware.h"
#include "wifi_manager.h"
#include "endpoints.h"
#include "device_id_manager.h"  // Dynamic device ID
#include <Update.h>
#include <WiFi.h>
#include <ArduinoOTA.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <WebServer.h>
#include <esp_https_ota.h>
#include <esp_http_client.h>
#include "security.h"
#include "time_sync.h"
#include "security/root_cert.h"

WebServer webServer(80);
unsigned long lastUpdateCheck = 0;

bool initOTA() {
  Serial.println("🔄 Initializing Secure OTA system...");
  
  // Check if WiFi is connected first
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ WiFi not connected - skipping OTA initialization");
    return false;
  }
  
  try {
#ifndef ENABLE_ELEGANT_OTA
    Serial.println("🔒 [PROD] ElegantOTA disabled for security");
    // Only enable secure esp_https_ota in production
#else
    // Start web server with ElegantOTA only in development
    startWebServer();
    Serial.printf("🔓 [DEV] Web interface: http://%s/\n", WiFi.localIP().toString().c_str());
#endif
    
    Serial.println("✅ Secure OTA system initialized");
    return true;
  } catch (const std::exception& e) {
    Serial.printf("❌ OTA initialization failed: %s\n", e.what());
    return false;
  } catch (...) {
    Serial.println("❌ OTA initialization failed with unknown error");
    return false;
  }
}

void handleOTA() {
#ifdef ENABLE_ELEGANT_OTA
  // Only handle web server in development - no ArduinoOTA to avoid WiFiUDP issues
  webServer.handleClient();
#endif
  
  // Check for updates periodically (every 2 hours)
  if (millis() - lastUpdateCheck > 7200000) {
    checkForUpdates();
    lastUpdateCheck = millis();
  }
}

bool checkForUpdates() {
  if (!isConfigured() || strlen(deviceConfig.server_host) == 0) {
    return false;
  }
  
  Serial.println("🔍 Checking for firmware updates securely...");
  
  // STRICT TIME GATE: Validate time before any TLS connection
  if (!isTimeSynced()) {
    Serial.println("❌ Time validation failed - blocking OTA TLS connection");
    return false;
  }
  
  // Use secure WiFiClientSecure with GTS Root R4 certificate
  WiFiClientSecure client;
  client.setCACert(ROOT_CA_PEM);
  
  HTTPClient http;
  String updateUrl = String("https://") + deviceConfig.server_host + FIRMWARE_MANIFEST_ENDPOINT;
  
  http.begin(client, updateUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Device-ID", deviceConfig.device_id);
  http.addHeader("Current-Version", FIRMWARE_VERSION);
  http.addHeader("Authorization", String("Bearer ") + DEVICE_SECRET_KEY);
  
  StaticJsonDocument<200> requestDoc;
  requestDoc["device_id"] = deviceConfig.device_id;
  requestDoc["current_version"] = FIRMWARE_VERSION;
  requestDoc["chip_model"] = ESP.getChipModel();
  
  String requestBody;
  serializeJson(requestDoc, requestBody);
  
  int httpResponseCode = http.POST(requestBody);
  
  if (httpResponseCode == 200) {
    String response = http.getString();
    FirmwareInfo firmwareInfo = parseUpdateResponse(response);
    
    if (firmwareInfo.version != FIRMWARE_VERSION || firmwareInfo.force_update) {
      Serial.printf("📦 New firmware available: %s\n", firmwareInfo.version.c_str());
      Serial.printf("Current: %s\n", FIRMWARE_VERSION);
      
      // Simple LED indication for update available
      setLEDColor("purple", 100);
      delay(500);
      clearLEDs();
      
      if (downloadAndInstallUpdate(firmwareInfo.download_url)) {
        Serial.println("✅ Update completed successfully!");
        return true;
      } else {
        Serial.println("❌ Update failed!");
        return false;
      }
    } else {
      Serial.println("✅ Firmware is up to date");
    }
  } else {
    Serial.printf("❌ Update check failed: %d\n", httpResponseCode);
  }
  
  http.end();
  return false;
}

FirmwareInfo parseUpdateResponse(const String& response) {
  FirmwareInfo info = {};
  
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, response);
  
  if (!error) {
    info.version = doc["version"].as<String>();
    info.download_url = doc["download_url"].as<String>();
    info.force_update = doc["force_update"] | false;
    info.file_size = doc["file_size"] | 0;
  }
  
  return info;
}

bool downloadAndInstallUpdate(const String& url) {
  if (url.length() == 0) {
    Serial.println("❌ Invalid download URL");
    return false;
  }
  
  Serial.printf("📥 Securely downloading update from: %s\n", url.c_str());
  
#ifdef PRODUCTION_BUILD
  // Use esp_https_ota for secure production updates
  return performSecureOTAUpdate(url);
#else
  // Development fallback - still use secure connection with GTS Root R4
  WiFiClientSecure client;
  client.setCACert(ROOT_CA_PEM);
  
  HTTPClient http;
  http.begin(client, url);
  
  int httpCode = http.GET();
  
  if (httpCode == 200) {
    int contentLength = http.getSize();
    
    if (contentLength <= 0) {
      Serial.println("❌ Invalid content length");
      http.end();
      return false;
    }
    
    Serial.printf("📦 Update size: %d bytes\n", contentLength);
    
    if (!Update.begin(contentLength)) {
      Serial.println("❌ Cannot begin update");
      http.end();
      return false;
    }
    
    WiFiClient* client = http.getStreamPtr();
    size_t written = 0;
    uint8_t buffer[1024];
    
    // Simple LED indication during update
    setLEDColor("orange", 50);
    
    while (http.connected() && written < contentLength) {
      size_t available = client->available();
      
      if (available) {
        int readBytes = client->readBytes(buffer, 
                                        ((available > sizeof(buffer)) ? sizeof(buffer) : available));
        
        size_t result = Update.write(buffer, readBytes);
        
        if (result != readBytes) {
          Serial.println("❌ Write failed");
          Update.abort();
          http.end();
          return false;
        }
        
        written += readBytes;
        
        int progress = (written * 100) / contentLength;
        if (progress % 10 == 0) {
          Serial.printf("Progress: %d%%\n", progress);
          // Simple LED progress indication - no undefined setLEDProgress function
          if (progress % 20 == 0) {
            setLEDColor("green", 30);
            delay(10);
            clearLEDs();
            delay(10);
          }
        }
      }
      delay(1);
    }
    
    if (Update.end(true)) {
      Serial.println("✅ Update completed successfully!");
      setLEDColor("green", 100);
      delay(1000);
      clearLEDs();
      
      Serial.println("🔄 Rebooting...");
      delay(1000);
      ESP.restart();
      return true;
    } else {
      Serial.printf("❌ Update failed: %s\n", Update.errorString());
    }
  } else {
    Serial.printf("❌ HTTP error: %d\n", httpCode);
  }
  
  http.end();
  return false;
#endif
}

#ifdef PRODUCTION_BUILD
bool performSecureOTAUpdate(const String& url) {
  Serial.println("🔒 Starting secure ESP-HTTPS-OTA update...");
  
  // ✅ Configure HTTP client for secure OTA with GTS Root R4 certificate
  esp_http_client_config_t http_cfg = {};
  http_cfg.url = url.c_str();
  http_cfg.cert_pem = ROOT_CA_PEM;
  http_cfg.timeout_ms = 30000;
  http_cfg.keep_alive_enable = true;
  
  // Add authentication headers
  String authHeader = String("Bearer ") + DEVICE_SECRET_KEY;
  String deviceIdHeader = String(deviceConfig.device_id);
  
  // Set LED indication
  setLEDColor("orange", 50);
  
  Serial.printf("🔒 Starting secure HTTPS OTA from: %s\n", url.c_str());
  esp_err_t ret = esp_https_ota(&http_cfg);
  
  if (ret == ESP_OK) {
    Serial.println("✅ Secure OTA update completed successfully!");
    setLEDColor("green", 100);
    delay(1000);
    Serial.println("🔄 Rebooting...");
    esp_restart();
    return true;
  } else {
    Serial.printf("❌ Secure OTA update failed: %s\n", esp_err_to_name(ret));
    // Error LED indication
    for (int i = 0; i < 3; i++) {
      setLEDColor("red", 100);
      delay(300);
      clearLEDs();
      delay(300);
    }
    return false;
  }
}
#endif

void startWebServer() {
#ifdef ENABLE_ELEGANT_OTA
  // Setup ElegantOTA with WebServer (NOT AsyncWebServer) - development only
  ElegantOTA.begin(&webServer);
#endif
  
  // Main page
  webServer.on("/", HTTP_GET, []() {
    String html = "<!DOCTYPE html><html><head><title>AI Teddy Bear OTA</title>";
    html += "<meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>";
    html += "<style>body { font-family: Arial; text-align: center; background: #f0f0f0; }";
    html += ".container { max-width: 400px; margin: 50px auto; padding: 20px; background: white; border-radius: 10px; }";
    html += "h1 { color: #333; }";
    html += ".info { background: #e8f4fd; padding: 15px; border-radius: 5px; margin: 10px 0; }";
    html += ".button { background: #007bff; color: white; padding: 12px 25px; border: none; border-radius: 5px; cursor: pointer; margin: 10px; text-decoration: none; display: inline-block; }";
    html += ".button:hover { background: #0056b3; }</style></head><body>";
    html += "<div class='container'><h1>AI Teddy Bear</h1><div class='info'>";
    html += "<p><strong>Device ID:</strong> " + String(DEVICE_ID) + "</p>";
    html += "<p><strong>Firmware:</strong> " + String(FIRMWARE_VERSION) + "</p>";
    html += "<p><strong>Free Memory:</strong> " + String(ESP.getFreeHeap()) + " bytes</p>";
    html += "<p><strong>Uptime:</strong> " + String(millis() / 1000) + " seconds</p></div>";
    html += "<a href='/update' class='button'>OTA Update</a>";
    html += "<a href='/restart' class='button'>Restart Device</a>";
    html += "</div></body></html>";
    
    webServer.send(200, "text/html", html);
  });
  
  // Restart endpoint
  webServer.on("/restart", HTTP_GET, []() {
    webServer.send(200, "text/html", "<h1>Restarting...</h1>");
    delay(1000);
    ESP.restart();
  });
  
  // Status endpoint
  webServer.on("/status", HTTP_GET, []() {
    StaticJsonDocument<300> doc;
    doc["device_id"] = getCurrentDeviceId();
    doc["firmware_version"] = FIRMWARE_VERSION;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["uptime"] = millis() / 1000;
    doc["wifi_ssid"] = WiFi.SSID();
    doc["wifi_rssi"] = WiFi.RSSI();
    doc["ip_address"] = WiFi.localIP().toString();
    
    String response;
    serializeJson(doc, response);
    
    webServer.send(200, "application/json", response);
  });
  
  webServer.begin();
  Serial.println("✅ Web server started");
}

void onOTAStart() {
  String type = (ArduinoOTA.getCommand() == U_FLASH) ? "sketch" : "filesystem";
  Serial.println("🔄 Start updating " + type);
  // No playUpdateAnimation - simple LED indication
  setLEDColor("blue", 100);
}

void onOTAEnd() {
  Serial.println("\n✅ OTA Update completed!");
  // No playSuccessAnimation - simple LED indication
  setLEDColor("green", 100);
  delay(1000);
  clearLEDs();
}

void onOTAProgress(unsigned int progress, unsigned int total) {
  static unsigned long lastPrint = 0;
  
  if (millis() - lastPrint > 1000) {
    Serial.printf("Progress: %u%%\n", (progress / (total / 100)));
    
    int percent = (progress * 100) / total;
    if (percent % 20 == 0) {
      setLEDColor("orange", 50);
      delay(100);
      clearLEDs();
    }
    
    lastPrint = millis();
  }
}

void onOTAError(ota_error_t error) {
  Serial.printf("❌ OTA Error[%u]: ", error);
  
  switch (error) {
    case OTA_AUTH_ERROR:
      Serial.println("Auth Failed");
      break;
    case OTA_BEGIN_ERROR:
      Serial.println("Begin Failed");
      break;
    case OTA_CONNECT_ERROR:
      Serial.println("Connect Failed");
      break;
    case OTA_RECEIVE_ERROR:
      Serial.println("Receive Failed");
      break;
    case OTA_END_ERROR:
      Serial.println("End Failed");
      break;
    default:
      Serial.println("Unknown Error");
      break;
  }
  
  // No playErrorAnimation - simple LED error indication
  for (int i = 0; i < 5; i++) {
    setLEDColor("red", 100);
    delay(200);
    clearLEDs();
    delay(200);
  }
  
  // No resetWiFiSettings - keep existing connection
}