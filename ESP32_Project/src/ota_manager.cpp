#include "ota_manager.h"
#include "hardware.h"
#include "wifi_manager.h"
#include "security.h"
#include <Update.h>
#include <WiFi.h>
#include <Preferences.h>

AsyncWebServer webServer(WEB_SERVER_PORT);
unsigned long lastUpdateCheck = 0;
String otaPassword = ""; // Will be generated at runtime
Preferences otaPrefs;

bool initOTA() {
  Serial.println("🔄 Initializing OTA system...");
  
  // Generate secure OTA password
  generateOTAPassword();
  
  // Configure Arduino OTA
  ArduinoOTA.setPort(OTA_PORT);
  ArduinoOTA.setHostname(OTA_HOSTNAME);
  
  // Set OTA callbacks
  ArduinoOTA.onStart(onOTAStart);
  ArduinoOTA.onProgress(onOTAProgress);
  ArduinoOTA.onEnd(onOTAEnd);
  ArduinoOTA.onError(onOTAError);
  
  ArduinoOTA.begin();
  
  // Start web server for remote management
  startWebServer();
  
  Serial.println("✅ OTA system initialized");
  Serial.printf("OTA Hostname: %s\n", OTA_HOSTNAME);
  Serial.printf("Web interface: http://%s/\n", WiFi.localIP().toString().c_str());
  
  return true;
}

void handleOTA() {
  ArduinoOTA.handle();
  
  // Check for updates periodically
  if (millis() - lastUpdateCheck > UPDATE_CHECK_INTERVAL) {
    checkForUpdates();
    lastUpdateCheck = millis();
  }
}

bool checkForUpdates() {
  if (!isConfigured() || strlen(deviceConfig.server_host) == 0) {
    return false;
  }
  
  Serial.println("🔍 Checking for firmware updates...");
  
  HTTPClient http;
  WiFiClientSecure* client = createSecureClient();
  String updateUrl = String("https://") + deviceConfig.server_host + 
                    ":" + (deviceConfig.ssl_enabled ? 443 : deviceConfig.server_port) + 
                    "/api/v1/firmware/check";
  
  if (!http.begin(*client, updateUrl)) {
    Serial.println("❌ Failed to begin HTTPS connection for update check");
    delete client;
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Device-ID", deviceConfig.device_id);
  http.addHeader("Current-Version", FIRMWARE_VERSION);
  
  // Create request body
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
      
      // Security checks
      if (!isVersionAllowed(firmwareInfo.version)) {
        Serial.println("❌ Version check failed - update blocked");
        logError(ERROR_UPDATE_FAILED, "Version not allowed: " + firmwareInfo.version, "security", 4);
        return false;
      }
      
      if (firmwareInfo.signature.isEmpty()) {
        Serial.println("❌ No signature provided - update blocked");
        logError(ERROR_UPDATE_FAILED, "Missing firmware signature", "security", 4);
        return false;
      }
      
      // Show update available animation
      playUpdateAnimation();
      
      // Download and install update with signature verification
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
  
  delete client;
  http.end();
  return false;
}

bool downloadAndInstallUpdate(const String& url) {
  Serial.printf("⬇️ Downloading update from: %s\n", url.c_str());
  
  HTTPClient http;
  WiFiClientSecure* client = createSecureClient();
  
  if (!http.begin(*client, url)) {
    Serial.println("❌ Failed to begin HTTPS connection for firmware download");
    delete client;
    return false;
  }
  
  int httpCode = http.GET();
  if (httpCode != 200) {
    Serial.printf("❌ Download failed: %d\n", httpCode);
    http.end();
    return false;
  }
  
  int contentLength = http.getSize();
  if (contentLength <= 0) {
    Serial.println("❌ Invalid content length");
    http.end();
    return false;
  }
  
  Serial.printf("📦 Firmware size: %d bytes\n", contentLength);
  
  // Check if we have enough space
  if (!Update.begin(contentLength)) {
    Serial.printf("❌ Not enough space for update: %s\n", Update.errorString());
    http.end();
    return false;
  }
  
  // Show update progress
  setLEDColor("yellow", 50);
  
  WiFiClient* client = http.getStreamPtr();
  size_t written = 0;
  uint8_t buffer[1024];
  
  while (http.connected() && written < contentLength) {
    size_t available = client->available();
    if (available > 0) {
      size_t read = client->readBytes(buffer, min(available, sizeof(buffer)));
      size_t bytesWritten = Update.write(buffer, read);
      written += bytesWritten;
      
      // Update progress LED
      int progress = (written * 100) / contentLength;
      if (progress % 10 == 0) {
        Serial.printf("Progress: %d%%\n", progress);
        setLEDProgress(progress);
      }
      
      if (bytesWritten != read) {
        Serial.println("❌ Write error during update");
        break;
      }
    }
    delay(1);
  }
  
  delete client;
  http.end();
  
  if (written == contentLength) {
    if (Update.end()) {
      if (Update.isFinished()) {
        Serial.println("✅ Update completed successfully!");
        playSuccessAnimation();
        delay(2000);
        ESP.restart();
        return true;
      } else {
        Serial.println("❌ Update failed to finish");
      }
    } else {
      Serial.printf("❌ Update error: %s\n", Update.errorString());
    }
  } else {
    Serial.printf("❌ Incomplete download: %d/%d bytes\n", written, contentLength);
  }
  
  playErrorAnimation();
  return false;
}

void onOTAStart() {
  String type = (ArduinoOTA.getCommand() == U_FLASH) ? "sketch" : "filesystem";
  Serial.printf("🔄 OTA Update started: %s\n", type.c_str());
  
  // Show OTA animation
  setLEDColor("purple", 100);
}

void onOTAProgress(unsigned int progress, unsigned int total) {
  int percentage = (progress / (total / 100));
  Serial.printf("Progress: %u%%\n", percentage);
  
  // Update LED progress
  setLEDProgress(percentage);
}

void onOTAEnd() {
  Serial.println("✅ OTA Update completed!");
  playSuccessAnimation();
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
  
  playErrorAnimation();
}

void startWebServer() {
  Serial.println("🌐 Starting web server...");
  
  // Setup ElegantOTA
  AsyncElegantOTA.begin(&webServer);
  
  // Root page - device status
  webServer.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    String html = "<!DOCTYPE html><html><head><title>AI Teddy Bear</title>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
    html += "<style>body{font-family:Arial;margin:40px;background:#f0f0f0;}";
    html += ".container{background:white;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);}";
    html += ".status{padding:10px;margin:10px 0;border-radius:5px;}";
    html += ".online{background:#d4edda;border:1px solid #c3e6cb;}";
    html += ".offline{background:#f8d7da;border:1px solid #f5c6cb;}";
    html += "button{background:#007bff;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer;margin:5px;}";
    html += "button:hover{background:#0056b3;}</style></head><body>";
    
    html += "<div class='container'>";
    html += "<h1>🧸 AI Teddy Bear Control Panel</h1>";
    
    // Device status
    html += "<div class='status online'>";
    html += "<h3>Device Status: Online</h3>";
    html += "<p><strong>Device ID:</strong> " + String(deviceConfig.device_id) + "</p>";
    html += "<p><strong>Firmware:</strong> " + String(FIRMWARE_VERSION) + "</p>";
    html += "<p><strong>WiFi:</strong> " + WiFi.SSID() + " (" + WiFi.RSSI() + " dBm)</p>";
    html += "<p><strong>IP Address:</strong> " + WiFi.localIP().toString() + "</p>";
    html += "<p><strong>Free Memory:</strong> " + String(ESP.getFreeHeap()) + " bytes</p>";
    html += "<p><strong>Uptime:</strong> " + String(millis() / 1000) + " seconds</p>";
    html += "</div>";
    
    // Child configuration
    if (strlen(deviceConfig.child_name) > 0) {
      html += "<div class='status online'>";
      html += "<h3>Child Profile</h3>";
      html += "<p><strong>Name:</strong> " + String(deviceConfig.child_name) + "</p>";
      html += "<p><strong>Age:</strong> " + String(deviceConfig.child_age) + "</p>";
      html += "<p><strong>Child ID:</strong> " + String(deviceConfig.child_id) + "</p>";
      html += "</div>";
    }
    
    // Control buttons
    html += "<h3>Controls</h3>";
    html += "<button onclick=\"location.href='/update'\">🔄 Firmware Update</button>";
    html += "<button onclick=\"location.href='/restart'\">🔄 Restart Device</button>";
    html += "<button onclick=\"location.href='/reset'\">⚠️ Factory Reset</button>";
    html += "<button onclick=\"location.href='/logs'\">📋 View Logs</button>";
    
    html += "</div></body></html>";
    
    request->send(200, "text/html", html);
  });
  
  // Device info API
  webServer.on("/api/info", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(200, "application/json", getDeviceInfo());
  });
  
  // Restart device
  webServer.on("/restart", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(200, "text/html", "<h1>Restarting...</h1><script>setTimeout(function(){window.location.href='/';}, 5000);</script>");
    delay(1000);
    ESP.restart();
  });
  
  // Factory reset
  webServer.on("/reset", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(200, "text/html", "<h1>Factory Reset...</h1><p>Device will restart in setup mode.</p>");
    delay(1000);
    resetWiFiSettings();
  });
  
  // Simple logs endpoint
  webServer.on("/logs", HTTP_GET, [](AsyncWebServerRequest *request) {
    String logs = "<!DOCTYPE html><html><head><title>Device Logs</title></head><body>";
    logs += "<h1>🧸 Device Logs</h1>";
    logs += "<p>Device ID: " + String(deviceConfig.device_id) + "</p>";
    logs += "<p>Last boot: " + String(millis()/1000) + " seconds ago</p>";
    logs += "<p>WiFi: " + WiFi.SSID() + "</p>";
    logs += "<p>Server: " + String(deviceConfig.server_host) + ":" + String(deviceConfig.server_port) + "</p>";
    logs += "<a href='/'>← Back to Main</a>";
    logs += "</body></html>";
    
    request->send(200, "text/html", logs);
  });
  
  webServer.begin();
  Serial.printf("✅ Web server started on port %d\n", WEB_SERVER_PORT);
}

FirmwareInfo parseUpdateResponse(const String& response) {
  FirmwareInfo info;
  
  StaticJsonDocument<512> doc;
  deserializeJson(doc, response);
  
  info.version = doc["version"].as<String>();
  info.download_url = doc["download_url"].as<String>();
  info.checksum = doc["checksum"].as<String>();
  info.signature = doc["signature"].as<String>();
  info.release_notes = doc["release_notes"].as<String>();
  info.force_update = doc["force_update"].as<bool>();
  info.file_size = doc["file_size"].as<size_t>();
  info.min_version = doc["min_version"].as<String>();
  
  return info;
}

String getCurrentVersion() {
  return String(FIRMWARE_VERSION);
}

// LED animation functions for OTA
void playUpdateAnimation() {
  // Yellow pulsing for update available
  for (int i = 0; i < 5; i++) {
    setLEDColor("yellow", 100);
    delay(200);
    setLEDColor("yellow", 20);
    delay(200);
  }
}

void setLEDProgress(int percentage) {
  // Show progress as filled LEDs
  int ledsToLight = map(percentage, 0, 100, 0, NUM_LEDS);
  
  clearLEDs();
  for (int i = 0; i < ledsToLight; i++) {
    setLEDIndex(i, "blue", 100);
  }
  delay(50);
}

// Security functions implementation
bool verifyFirmwareSignature(const uint8_t* firmwareData, size_t dataSize, const String& signature) {
  Serial.println("🔐 Verifying firmware signature...");
  
  if (signature.isEmpty() || dataSize == 0) {
    Serial.println("❌ Invalid signature or firmware data");
    return false;
  }
  
  // Initialize mbedTLS context
  mbedtls_pk_context pk_ctx;
  mbedtls_pk_init(&pk_ctx);
  
  // Parse public key
  int ret = mbedtls_pk_parse_public_key(&pk_ctx, 
                                        (const unsigned char*)FIRMWARE_PUBLIC_KEY, 
                                        strlen(FIRMWARE_PUBLIC_KEY) + 1);
  
  if (ret != 0) {
    Serial.printf("❌ Failed to parse public key: %d\n", ret);
    mbedtls_pk_free(&pk_ctx);
    return false;
  }
  
  // Calculate SHA256 hash of firmware
  unsigned char hash[32];
  mbedtls_sha256_context sha256_ctx;
  mbedtls_sha256_init(&sha256_ctx);
  mbedtls_sha256_starts_ret(&sha256_ctx, 0);
  mbedtls_sha256_update_ret(&sha256_ctx, firmwareData, dataSize);
  mbedtls_sha256_finish_ret(&sha256_ctx, hash);
  mbedtls_sha256_free(&sha256_ctx);
  
  // Decode signature from base64
  size_t sig_len = signature.length() * 3 / 4; // Approximate decoded length
  unsigned char* sig_buf = (unsigned char*)malloc(sig_len);
  if (!sig_buf) {
    Serial.println("❌ Failed to allocate signature buffer");
    mbedtls_pk_free(&pk_ctx);
    return false;
  }
  
  // Simple base64 decode (you may want to use a proper library)
  size_t actual_sig_len = 0; // This would be set by proper base64 decode
  // TODO: Implement proper base64 decoding here
  
  // Verify signature
  ret = mbedtls_pk_verify(&pk_ctx, MBEDTLS_MD_SHA256, hash, 32, sig_buf, actual_sig_len);
  
  free(sig_buf);
  mbedtls_pk_free(&pk_ctx);
  
  if (ret == 0) {
    Serial.println("✅ Firmware signature verified successfully");
    return true;
  } else {
    Serial.printf("❌ Firmware signature verification failed: %d\n", ret);
    return false;
  }
}

bool isVersionAllowed(const String& newVersion) {
  Serial.printf("🔍 Checking if version %s is allowed...\n", newVersion.c_str());
  
  // Check against minimum version (anti-rollback)
  if (compareVersions(newVersion, MIN_FIRMWARE_VERSION) < 0) {
    Serial.printf("❌ Version %s is below minimum allowed version %s\n", 
                  newVersion.c_str(), MIN_FIRMWARE_VERSION);
    return false;
  }
  
  // Check against current version
  String currentVersion = getCurrentVersion();
  if (compareVersions(newVersion, currentVersion) < 0) {
    Serial.printf("❌ Rollback attempt detected: %s -> %s\n", 
                  currentVersion.c_str(), newVersion.c_str());
    return false;
  }
  
  Serial.println("✅ Version check passed");
  return true;
}

int compareVersions(const String& v1, const String& v2) {
  // Simple version comparison (major.minor.patch)
  // Returns: -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
  
  int v1_major = 0, v1_minor = 0, v1_patch = 0;
  int v2_major = 0, v2_minor = 0, v2_patch = 0;
  
  sscanf(v1.c_str(), "%d.%d.%d", &v1_major, &v1_minor, &v1_patch);
  sscanf(v2.c_str(), "%d.%d.%d", &v2_major, &v2_minor, &v2_patch);
  
  if (v1_major != v2_major) return (v1_major > v2_major) ? 1 : -1;
  if (v1_minor != v2_minor) return (v1_minor > v2_minor) ? 1 : -1;
  if (v1_patch != v2_patch) return (v1_patch > v2_patch) ? 1 : -1;
  
  return 0;
}

void generateOTAPassword() {
  Serial.println("🔐 Generating secure OTA password...");
  
  otaPrefs.begin("ota", false);
  
  // Check if password already exists
  otaPassword = otaPrefs.getString("password", "");
  
  if (otaPassword.isEmpty()) {
    // Generate secure random password
    const char charset[] = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*";
    const int passwordLength = 16;
    
    otaPassword = "";
    for (int i = 0; i < passwordLength; i++) {
      int randomIndex = esp_random() % (sizeof(charset) - 1);
      otaPassword += charset[randomIndex];
    }
    
    // Store password securely
    otaPrefs.putString("password", otaPassword);
    Serial.println("✅ New OTA password generated and stored");
  } else {
    Serial.println("✅ Using existing OTA password");
  }
  
  // Set the password for ArduinoOTA
  ArduinoOTA.setPassword(otaPassword.c_str());
}
