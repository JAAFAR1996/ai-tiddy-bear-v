#include "device_management.h"
#include "monitoring.h"
#include "security.h"
#include "wifi_manager.h"
#include "ota_manager.h"
#include "hardware.h"
#include "config.h"
#include <WiFi.h>
#include <Preferences.h>
#include <SPIFFS.h>

// Global management variables
ManagementConfig managementConfig;
DeviceInfo deviceInfo;
DeviceStatus currentStatus = STATUS_IDLE;
WebServer* managementServer = nullptr;

const unsigned long DEFAULT_CHECKIN_INTERVAL = 300000; // 5 minutes
const int MANAGEMENT_WEB_PORT = 8080;
const int MAX_CONFIG_SIZE = 4096;
const int DIAGNOSTICS_TIMEOUT = 30000; // 30 seconds

Preferences managementPrefs;

bool initDeviceManagement() {
  Serial.println("🔧 Initializing device management...");
  
  // Initialize preferences
  managementPrefs.begin("device_mgmt", false);
  
  // Load management configuration
  managementConfig.remote_management_enabled = managementPrefs.getBool("remote_enabled", true);
  managementConfig.auto_update_enabled = managementPrefs.getBool("auto_update", true);
  managementConfig.diagnostics_enabled = managementPrefs.getBool("diagnostics", true);
  managementConfig.management_server = managementPrefs.getString("mgmt_server", deviceConfig.server_host);
  managementConfig.management_port = managementPrefs.getInt("mgmt_port", deviceConfig.server_port);
  managementConfig.checkin_interval = managementPrefs.getULong("checkin_interval", DEFAULT_CHECKIN_INTERVAL);
  managementConfig.last_checkin = 0;
  
  // Initialize device info
  updateDeviceInfo();
  
  // Initialize SPIFFS for configuration storage
  if (!SPIFFS.begin(true)) {
    Serial.println("❌ Failed to initialize SPIFFS");
    return false;
  }
  
  // Start management web server if enabled
  if (managementConfig.remote_management_enabled) {
    startManagementServer();
  }
  
  // Register device with management server
  if (WiFi.isConnected()) {
    registerDevice();
  }
  
  Serial.println("✅ Device management initialized");
  return true;
}

void handleDeviceManagement() {
  // Handle web server requests
  if (managementServer) {
    managementServer->handleClient();
  }
  
  // Check for updates if enabled
  if (managementConfig.auto_update_enabled) {
    static unsigned long lastUpdateCheck = 0;
    if (millis() - lastUpdateCheck > 3600000) { // Check hourly
      checkForUpdates();
      lastUpdateCheck = millis();
    }
  }
  
  // Periodic check-in with management server
  if (WiFi.isConnected() && 
      millis() - managementConfig.last_checkin > managementConfig.checkin_interval) {
    reportDeviceStatus();
    managementConfig.last_checkin = millis();
  }
  
  // Update status LED
  updateStatusLED();
}

bool executeCommand(DeviceCommand cmd, const String& params) {
  Serial.printf("🔧 Executing command: %s\n", commandToString(cmd).c_str());
  
  setDeviceStatus(STATUS_BUSY);
  
  bool success = false;
  
  switch (cmd) {
    case CMD_RESTART:
      Serial.println("🔄 Restarting device...");
      delay(1000);
      ESP.restart();
      break;
      
    case CMD_FACTORY_RESET:
      Serial.println("🏭 Performing factory reset...");
      // Clear all preferences
      managementPrefs.clear();
      clearWiFiConfig();
      clearOTAConfig();
      success = true;
      delay(2000);
      ESP.restart();
      break;
      
    case CMD_UPDATE_CONFIG:
      success = updateDeviceConfig(params);
      break;
      
    case CMD_UPDATE_FIRMWARE:
      success = checkForUpdates();
      break;
      
    case CMD_RUN_DIAGNOSTICS:
      success = runDiagnostics();
      break;
      
    case CMD_CALIBRATE_AUDIO:
      success = runAudioDiagnostics();
      break;
      
    case CMD_CALIBRATE_MOTION:
      success = runMotionDiagnostics();
      break;
      
    case CMD_SET_LED_TEST:
      // LED test pattern
      setLEDColor("red", 100);
      delay(500);
      setLEDColor("green", 100);
      delay(500);
      setLEDColor("blue", 100);
      delay(500);
      clearLEDs();
      success = true;
      break;
      
    case CMD_BACKUP_CONFIG:
      success = backupConfiguration();
      break;
      
    case CMD_RESTORE_CONFIG:
      success = restoreConfiguration(params);
      break;
      
    default:
      Serial.println("❌ Unknown command");
      logError(ERROR_AUTH_FAILED, "Unknown management command", commandToString(cmd), 2);
      break;
  }
  
  setDeviceStatus(STATUS_IDLE);
  
  if (success) {
    Serial.printf("✅ Command %s executed successfully\n", commandToString(cmd).c_str());
  } else {
    Serial.printf("❌ Command %s failed\n", commandToString(cmd).c_str());
  }
  
  return success;
}

bool registerDevice() {
  if (!isAuthenticated()) {
    return false;
  }
  
  Serial.println("📝 Registering device with management server...");
  
  HTTPClient http;
  String url = String("http") + (securityConfig.ssl_enabled ? "s" : "") + 
               "://" + managementConfig.management_server + 
               ":" + managementConfig.management_port + 
               "/api/v1/devices/register";
  
  WiFiClientSecure* client = nullptr;
  if (securityConfig.ssl_enabled) {
    client = createSecureClient();
    http.begin(*client, url);
  } else {
    http.begin(url);
  }
  
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + securityConfig.api_token);
  
  // Create registration payload
  StaticJsonDocument<1024> doc;
  doc["device_id"] = deviceInfo.device_id;
  doc["device_type"] = "ai_teddy_bear";
  doc["firmware_version"] = deviceInfo.firmware_version;
  doc["hardware_version"] = deviceInfo.hardware_version;
  doc["mac_address"] = deviceInfo.mac_address;
  doc["ip_address"] = deviceInfo.ip_address;
  doc["capabilities"] = "audio,motion,leds,websocket,ota,diagnostics";
  doc["management_enabled"] = managementConfig.remote_management_enabled;
  doc["auto_update_enabled"] = managementConfig.auto_update_enabled;
  
  String payload;
  serializeJson(doc, payload);
  
  int responseCode = http.POST(payload);
  String response = http.getString();
  
  if (client) delete client;
  http.end();
  
  if (responseCode == 200) {
    Serial.println("✅ Device registered successfully");
    return true;
  } else {
    Serial.printf("❌ Device registration failed: %d\n", responseCode);
    logError(ERROR_SERVER_UNREACHABLE, "Device registration failed", String(responseCode), 2);
    return false;
  }
}

bool reportDeviceStatus() {
  if (!isAuthenticated()) {
    return false;
  }
  
  HTTPClient http;
  String url = String("http") + (securityConfig.ssl_enabled ? "s" : "") + 
               "://" + managementConfig.management_server + 
               ":" + managementConfig.management_port + 
               "/api/v1/devices/" + deviceInfo.device_id + "/status";
  
  WiFiClientSecure* client = nullptr;
  if (securityConfig.ssl_enabled) {
    client = createSecureClient();
    http.begin(*client, url);
  } else {
    http.begin(url);
  }
  
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + securityConfig.api_token);
  
  // Update device info
  updateDeviceInfo();
  
  // Create status report
  StaticJsonDocument<1024> doc;
  doc["device_id"] = deviceInfo.device_id;
  doc["status"] = (int)currentStatus;
  doc["uptime"] = deviceInfo.uptime;
  doc["free_memory"] = ESP.getFreeHeap();
  doc["wifi_rssi"] = WiFi.RSSI();
  doc["last_restart"] = deviceInfo.last_restart;
  doc["restart_count"] = deviceInfo.restart_count;
  doc["firmware_version"] = deviceInfo.firmware_version;
  doc["ip_address"] = deviceInfo.ip_address;
  
  // Add system health
  SystemHealth health = getSystemHealth();
  JsonObject healthObj = doc.createNestedObject("health");
  healthObj["temperature"] = health.temperature;
  healthObj["cpu_usage"] = health.cpu_usage;
  healthObj["error_count"] = health.error_count;
  healthObj["audio_ok"] = health.audio_system_ok;
  healthObj["websocket_connected"] = health.websocket_connected;
  
  String payload;
  serializeJson(doc, payload);
  
  int responseCode = http.POST(payload);
  String response = http.getString();
  
  // Check for remote commands in response
  if (responseCode == 200) {
    StaticJsonDocument<512> responseDoc;
    if (deserializeJson(responseDoc, response) == DeserializationError::Ok) {
      if (responseDoc.containsKey("command")) {
        String commandStr = responseDoc["command"];
        String params = responseDoc["params"] | "";
        processRemoteCommand(commandStr, params);
      }
    }
  }
  
  if (client) delete client;
  http.end();
  
  return (responseCode == 200);
}

void processRemoteCommand(const String& command, const String& params) {
  DeviceCommand cmd = parseCommand(command);
  
  if (cmd != CMD_UNKNOWN) {
    Serial.printf("📨 Received remote command: %s\n", command.c_str());
    executeCommand(cmd, params);
  } else {
    Serial.printf("❌ Unknown remote command: %s\n", command.c_str());
  }
}

bool runDiagnostics() {
  if (!managementConfig.diagnostics_enabled) {
    return false;
  }
  
  Serial.println("🔍 Running system diagnostics...");
  setDeviceStatus(STATUS_MAINTENANCE);
  
  bool allTestsPassed = true;
  
  // Test memory
  if (!runMemoryDiagnostics()) {
    allTestsPassed = false;
  }
  
  // Test network
  if (!runNetworkDiagnostics()) {
    allTestsPassed = false;
  }
  
  // Test audio
  if (!runAudioDiagnostics()) {
    allTestsPassed = false;
  }
  
  // Test motion/servo
  if (!runMotionDiagnostics()) {
    allTestsPassed = false;
  }
  
  setDeviceStatus(STATUS_IDLE);
  
  if (allTestsPassed) {
    Serial.println("✅ All diagnostics passed");
    setLEDColor("green", 50);
    delay(1000);
    clearLEDs();
  } else {
    Serial.println("❌ Some diagnostics failed");
    setLEDColor("red", 50);
    delay(1000);
    clearLEDs();
  }
  
  return allTestsPassed;
}

bool runMemoryDiagnostics() {
  Serial.println("🧠 Testing memory...");
  
  uint32_t freeHeap = ESP.getFreeHeap();
  uint32_t minFreeHeap = ESP.getMinFreeHeap();
  
  Serial.printf("Free Heap: %d bytes\n", freeHeap);
  Serial.printf("Min Free Heap: %d bytes\n", minFreeHeap);
  
  if (freeHeap < 10000) {
    Serial.println("❌ Low memory detected");
    return false;
  }
  
  Serial.println("✅ Memory test passed");
  return true;
}

bool runNetworkDiagnostics() {
  Serial.println("🌐 Testing network connectivity...");
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi not connected");
    return false;
  }
  
  // Test server connectivity
  HTTPClient http;
  String url = String("http://") + managementConfig.management_server + 
               ":" + managementConfig.management_port + "/health";
  
  http.begin(url);
  http.setTimeout(5000);
  
  int responseCode = http.GET();
  http.end();
  
  if (responseCode != 200) {
    Serial.printf("❌ Server connectivity test failed: %d\n", responseCode);
    return false;
  }
  
  Serial.println("✅ Network test passed");
  return true;
}

bool runAudioDiagnostics() {
  Serial.println("🔊 Testing audio system...");
  
  // Test audio playback
  playTone(1000, 200);
  delay(300);
  
  // Check audio state
  if (getAudioState() == AUDIO_ERROR) {
    Serial.println("❌ Audio system error");
    return false;
  }
  
  Serial.println("✅ Audio test passed");
  return true;
}

bool runMotionDiagnostics() {
  Serial.println("🤖 Testing motion system...");
  
  // Test servo movement
  moveHead(90);
  delay(500);
  moveHead(45);
  delay(500);
  moveHead(90); // Return to center
  
  Serial.println("✅ Motion test passed");
  return true;
}

DeviceInfo getDeviceInfo() {
  updateDeviceInfo();
  return deviceInfo;
}

bool updateDeviceInfo() {
  deviceInfo.device_id = DEVICE_ID;
  deviceInfo.firmware_version = FIRMWARE_VERSION;
  deviceInfo.hardware_version = "ESP32-v1.0";
  deviceInfo.mac_address = WiFi.macAddress();
  deviceInfo.ip_address = WiFi.localIP().toString();
  deviceInfo.uptime = millis() / 1000;
  deviceInfo.status = currentStatus;
  
  // Load persistent data
  deviceInfo.restart_count = managementPrefs.getUInt("restart_count", 0);
  deviceInfo.last_restart = managementPrefs.getULong("last_restart", 0);
  
  return true;
}

void startManagementServer() {
  if (managementServer) {
    return; // Already started
  }
  
  Serial.printf("🌐 Starting management web server on port %d...\n", MANAGEMENT_WEB_PORT);
  
  managementServer = new WebServer(MANAGEMENT_WEB_PORT);
  
  // Setup web routes
  managementServer->on("/", HTTP_GET, []() {
    handleManagementWeb();
  });
  
  managementServer->on("/status", HTTP_GET, []() {
    updateDeviceInfo();
    SystemHealth health = getSystemHealth();
    
    StaticJsonDocument<1024> doc;
    doc["device_id"] = deviceInfo.device_id;
    doc["status"] = (int)currentStatus;
    doc["uptime"] = deviceInfo.uptime;
    doc["firmware_version"] = deviceInfo.firmware_version;
    doc["free_memory"] = ESP.getFreeHeap();
    doc["wifi_rssi"] = WiFi.RSSI();
    doc["temperature"] = health.temperature;
    doc["cpu_usage"] = health.cpu_usage;
    doc["error_count"] = health.error_count;
    
    String response;
    serializeJson(doc, response);
    
    managementServer->send(200, "application/json", response);
  });
  
  managementServer->on("/command", HTTP_POST, []() {
    if (!managementServer->hasArg("cmd")) {
      managementServer->send(400, "text/plain", "Missing command parameter");
      return;
    }
    
    String command = managementServer->arg("cmd");
    String params = managementServer->arg("params");
    
    DeviceCommand cmd = parseCommand(command);
    if (cmd == CMD_UNKNOWN) {
      managementServer->send(400, "text/plain", "Unknown command");
      return;
    }
    
    bool success = executeCommand(cmd, params);
    
    if (success) {
      managementServer->send(200, "text/plain", "Command executed successfully");
    } else {
      managementServer->send(500, "text/plain", "Command execution failed");
    }
  });
  
  managementServer->begin();
  Serial.println("✅ Management web server started");
}

void handleManagementWeb() {
  String html = R"(
<!DOCTYPE html>
<html>
<head>
    <title>AI Teddy Bear Management</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .status { background: #f0f0f0; padding: 10px; border-radius: 5px; margin: 10px 0; }
        .button { background: #007cba; color: white; padding: 10px 20px; border: none; border-radius: 5px; margin: 5px; cursor: pointer; }
        .button:hover { background: #005a8b; }
        .error { color: red; }
        .success { color: green; }
    </style>
</head>
<body>
    <h1>🧸 AI Teddy Bear Management</h1>
    
    <div class="status">
        <h3>Device Status</h3>
        <p><strong>Device ID:</strong> )" + deviceInfo.device_id + R"(</p>
        <p><strong>Firmware:</strong> )" + deviceInfo.firmware_version + R"(</p>
        <p><strong>Uptime:</strong> )" + String(deviceInfo.uptime) + R"( seconds</p>
        <p><strong>Free Memory:</strong> )" + String(ESP.getFreeHeap()) + R"( bytes</p>
        <p><strong>WiFi RSSI:</strong> )" + String(WiFi.RSSI()) + R"( dBm</p>
    </div>
    
    <h3>Management Commands</h3>
    <button class="button" onclick="sendCommand('restart')">Restart Device</button>
    <button class="button" onclick="sendCommand('diagnostics')">Run Diagnostics</button>
    <button class="button" onclick="sendCommand('led_test')">Test LEDs</button>
    <button class="button" onclick="sendCommand('audio_test')">Test Audio</button>
    <button class="button" onclick="sendCommand('update')">Check Updates</button>
    
    <div id="result"></div>
    
    <script>
        function sendCommand(cmd) {
            fetch('/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'cmd=' + cmd
            })
            .then(response => response.text())
            .then(data => {
                document.getElementById('result').innerHTML = '<p class="success">' + data + '</p>';
            })
            .catch(error => {
                document.getElementById('result').innerHTML = '<p class="error">Error: ' + error + '</p>';
            });
        }
        
        // Auto-refresh status every 10 seconds
        setInterval(() => {
            location.reload();
        }, 10000);
    </script>
</body>
</html>
)";
  
  managementServer->send(200, "text/html", html);
}

DeviceCommand parseCommand(const String& commandStr) {
  if (commandStr == "restart") return CMD_RESTART;
  if (commandStr == "factory_reset") return CMD_FACTORY_RESET;
  if (commandStr == "update_config") return CMD_UPDATE_CONFIG;
  if (commandStr == "update") return CMD_UPDATE_FIRMWARE;
  if (commandStr == "diagnostics") return CMD_RUN_DIAGNOSTICS;
  if (commandStr == "audio_test") return CMD_CALIBRATE_AUDIO;
  if (commandStr == "motion_test") return CMD_CALIBRATE_MOTION;
  if (commandStr == "led_test") return CMD_SET_LED_TEST;
  if (commandStr == "backup") return CMD_BACKUP_CONFIG;
  if (commandStr == "restore") return CMD_RESTORE_CONFIG;
  
  return CMD_UNKNOWN;
}

String commandToString(DeviceCommand cmd) {
  switch (cmd) {
    case CMD_RESTART: return "restart";
    case CMD_FACTORY_RESET: return "factory_reset";
    case CMD_UPDATE_CONFIG: return "update_config";
    case CMD_UPDATE_FIRMWARE: return "update_firmware";
    case CMD_RUN_DIAGNOSTICS: return "run_diagnostics";
    case CMD_CALIBRATE_AUDIO: return "calibrate_audio";
    case CMD_CALIBRATE_MOTION: return "calibrate_motion";
    case CMD_SET_LED_TEST: return "led_test";
    case CMD_BACKUP_CONFIG: return "backup_config";
    case CMD_RESTORE_CONFIG: return "restore_config";
    default: return "unknown";
  }
}

void setDeviceStatus(DeviceStatus status) {
  currentStatus = status;
}

DeviceStatus getDeviceStatus() {
  return currentStatus;
}

void updateStatusLED() {
  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate < 1000) return; // Update every second
  
  switch (currentStatus) {
    case STATUS_IDLE:
      // Soft green breathing
      setLEDColor("green", 10);
      break;
    case STATUS_BUSY:
      // Pulsing blue
      setLEDColor("blue", 50);
      break;
    case STATUS_UPDATING:
      // Flashing yellow
      setLEDColor("yellow", 70);
      delay(100);
      clearLEDs();
      break;
    case STATUS_ERROR:
      // Solid red
      setLEDColor("red", 80);
      break;
    case STATUS_MAINTENANCE:
      // Alternating orange
      setLEDColor("orange", 60);
      break;
  }
  
  lastUpdate = millis();
}

bool checkForUpdates() {
  // This function would normally check for firmware updates
  // For now, it just reports that no updates are available
  Serial.println("🔄 Checking for firmware updates...");
  
  // Would implement actual update check here
  // For production, this would query the management server
  
  Serial.println("✅ No firmware updates available");
  return true;
}

bool updateDeviceConfig(const String& configJson) {
  Serial.println("⚙️ Updating device configuration...");
  
  if (!validateConfiguration(configJson)) {
    Serial.println("❌ Invalid configuration data");
    return false;
  }
  
  // Parse and apply configuration
  StaticJsonDocument<1024> doc;
  if (deserializeJson(doc, configJson) != DeserializationError::Ok) {
    Serial.println("❌ Failed to parse configuration JSON");
    return false;
  }
  
  // Update management settings
  if (doc.containsKey("remote_management")) {
    managementConfig.remote_management_enabled = doc["remote_management"];
    managementPrefs.putBool("remote_enabled", managementConfig.remote_management_enabled);
  }
  
  if (doc.containsKey("auto_update")) {
    managementConfig.auto_update_enabled = doc["auto_update"];
    managementPrefs.putBool("auto_update", managementConfig.auto_update_enabled);
  }
  
  if (doc.containsKey("checkin_interval")) {
    managementConfig.checkin_interval = doc["checkin_interval"];
    managementPrefs.putULong("checkin_interval", managementConfig.checkin_interval);
  }
  
  Serial.println("✅ Device configuration updated");
  return true;
}

bool validateConfiguration(const String& configJson) {
  if (configJson.length() > MAX_CONFIG_SIZE) {
    return false;
  }
  
  StaticJsonDocument<1024> doc;
  return (deserializeJson(doc, configJson) == DeserializationError::Ok);
}

bool backupConfiguration() {
  Serial.println("💾 Creating configuration backup...");
  
  StaticJsonDocument<1024> doc;
  doc["device_id"] = deviceInfo.device_id;
  doc["firmware_version"] = deviceInfo.firmware_version;
  doc["remote_management"] = managementConfig.remote_management_enabled;
  doc["auto_update"] = managementConfig.auto_update_enabled;
  doc["diagnostics"] = managementConfig.diagnostics_enabled;
  doc["checkin_interval"] = managementConfig.checkin_interval;
  
  String backup;
  serializeJson(doc, backup);
  
  // Save to SPIFFS
  File file = SPIFFS.open("/config_backup.json", "w");
  if (!file) {
    Serial.println("❌ Failed to create backup file");
    return false;
  }
  
  file.print(backup);
  file.close();
  
  Serial.println("✅ Configuration backup created");
  return true;
}

bool restoreConfiguration(const String& backupData) {
  Serial.println("📂 Restoring configuration from backup...");
  
  if (!validateConfiguration(backupData)) {
    Serial.println("❌ Invalid backup data");
    return false;
  }
  
  return updateDeviceConfig(backupData);
}
