#include "wifi_portal.h"
#include "hardware.h"
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include "config_manager.h"  // Access ConfigManager & TeddyConfig
#include <esp_task_wdt.h>

// Setup mode handler for main loop – يدير بوابة الإعداد إن كانت نشطة
void handleSetupMode() {
  // عالج البوابة إن كانت فعّالة
  handleWiFiPortal();
}

// WiFi Portal Configuration
WebServer portalServer(80);
DNSServer dnsServer;
bool portalActive = false;
bool configurationComplete = false;
unsigned long portalStartTime = 0;
const unsigned long PORTAL_TIMEOUT = 300000; // 5 minutes timeout

// Access Point Configuration
const char* AP_SSID = "TeddyBear_Setup";
// Open network (no password)
const char* AP_PASSWORD = "";
const IPAddress AP_IP(192, 168, 4, 1);
const IPAddress AP_GATEWAY(192, 168, 4, 1);
const IPAddress AP_SUBNET(255, 255, 255, 0);

bool startWiFiPortal() {
    Serial.println("Starting WiFi Configuration Portal...");
    
    // Keep existing STA attempt; we'll run AP concurrently to avoid long waits
    
    // Configure Access Point
    // Use concurrent AP+STA so device can keep trying STA while AP is visible
    WiFi.mode(WIFI_AP_STA);
    // Limit AP TX power to reduce current spikes on weak supplies
    WiFi.setTxPower(WIFI_POWER_11dBm);
    WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET);
    // Explicit channel and allow up to 4 clients (open network if password empty)
    bool apStarted = WiFi.softAP(AP_SSID, AP_PASSWORD, 1 /*channel*/, 0 /*visible*/, 4 /*max conn*/);
    if (!apStarted) {
        Serial.println("SoftAP start failed on channel 1, retrying on 6...");
        apStarted = WiFi.softAP(AP_SSID, AP_PASSWORD, 6, 0, 4);
    }
    if (!apStarted) {
        Serial.println("SoftAP start failed on channel 6, retrying on 11...");
        apStarted = WiFi.softAP(AP_SSID, AP_PASSWORD, 11, 0, 4);
    }
    
    if (!apStarted) {
        Serial.println("Failed to start Access Point");
        return false;
    }
    
    Serial.printf("Access Point started: %s\n", AP_SSID);
    Serial.printf("Connect to WiFi: %s (open network)\n", AP_SSID);
    Serial.printf("Open browser: http://%s\n", AP_IP.toString().c_str());
    
    // Start DNS server for captive portal
    dnsServer.start(53, "*", AP_IP);
    
    // Setup web server routes
    setupPortalRoutes();
    
    // Start web server
    portalServer.begin();
    
    portalActive = true;
    portalStartTime = millis();
    configurationComplete = false;
    
    // Visual indication - pulsing blue
    setLEDColor("blue", 100);
    
    return true;
}

void setupPortalRoutes() {
    // Main configuration page
    portalServer.on("/", HTTP_GET, handlePortalRoot);
    portalServer.on("/config", HTTP_GET, handlePortalRoot);
    portalServer.on("/setup", HTTP_GET, handlePortalRoot);
    
    // API endpoints
    portalServer.on("/scan", HTTP_GET, handleNetworkScan);
    portalServer.on("/connect", HTTP_POST, handleWiFiConnect);
    portalServer.on("/status", HTTP_GET, handleConnectionStatus);
    portalServer.on("/device", HTTP_POST, handleDeviceConfig);
    portalServer.on("/restart", HTTP_POST, handleRestart);
    
    // Captive portal - redirect all requests to main page
    portalServer.onNotFound(handlePortalRoot);
    
    Serial.println("Portal routes configured");
}

void handlePortalRoot() {
    String html = generatePortalHTML();
    portalServer.send(200, "text/html", html);
}

String generatePortalHTML() {
    String html = "<!DOCTYPE html><html><head>";
    html += "<meta charset='UTF-8'>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
    html += "<title>AI Teddy Bear Setup</title>";
    html += "<style>";
    html += "body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }";
    html += ".container { max-width: 400px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }";
    html += ".header { text-align: center; color: #333; margin-bottom: 20px; }";
    html += ".section { margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px; }";
    html += "input, select { width: 100%; padding: 10px; margin: 5px 0; border: 1px solid #ddd; border-radius: 5px; }";
    html += ".btn { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; margin: 5px 0; }";
    html += ".btn:hover { background: #0056b3; }";
    html += ".btn-warning { background: #ffc107; color: #212529; }";
    html += ".btn-success { background: #28a745; }";
    html += ".status { padding: 10px; margin: 10px 0; border-radius: 5px; text-align: center; }";
    html += ".success { background: #d4edda; color: #155724; }";
    html += ".error { background: #f8d7da; color: #721c24; }";
    html += ".info { background: #d1ecf1; color: #0c5460; }";
    html += ".network-list { max-height: 200px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px; }";
    html += ".network-item { padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; }";
    html += ".network-item:hover { background: #f8f9fa; }";
    html += ".hidden { display: none; }";
    html += "</style></head><body>";
    
    html += "<div class='container'>";
    html += "<div class='header'><h1>AI Teddy Bear</h1><p>WiFi Setup Portal</p></div>";
    
    // WiFi Configuration Section
    html += "<div class='section'>";
    html += "<h3>WiFi Configuration</h3>";
    html += "<button class='btn btn-warning' onclick='scanNetworks()'>Scan Networks</button>";
    html += "<div id='networkList' class='hidden'>";
    html += "<label>Available Networks:</label>";
    html += "<div class='network-list' id='networks'><div>Scanning...</div></div>";
    html += "</div>";
    html += "<label>Network Name (SSID):</label>";
    html += "<input type='text' id='ssid' placeholder='Select from list or type manually'>";
    html += "<label>Password:</label>";
    html += "<input type='password' id='password' placeholder='Network password'>";
    html += "<button class='btn' onclick='connectWiFi()'>Connect to Network</button>";
    html += "<div id='wifiStatus'></div>";
    html += "</div>";
    
    // Device Information Section
    html += "<div class='section'>";
    html += "<h3>Device Information</h3>";
    html += "<p><strong>Device ID:</strong> teddy-001</p>";
    html += "<p><strong>Firmware Version:</strong> 1.0.0</p>";
    html += "<p><strong>MAC Address:</strong> " + WiFi.macAddress() + "</p>";
    html += "<div class='status info'><p>Child profile will be configured via mobile app</p></div>";
    html += "</div>";
    
    // Control Section
    html += "<div class='section'>";
    html += "<h3>Control</h3>";
    html += "<button class='btn btn-success' onclick='checkStatus()'>Check Status</button>";
    html += "<button class='btn btn-warning' onclick='restartDevice()'>Restart Device</button>";
    html += "</div>";
    
    html += "<div id='generalStatus'></div>";
    html += "</div>";
    
    // JavaScript
    html += "<script>";
    html += "function scanNetworks() {";
    html += "  document.getElementById('networkList').classList.remove('hidden');";
    html += "  document.getElementById('networks').innerHTML = 'Scanning...';";
    html += "  fetch('/scan').then(response => response.json()).then(data => {";
    html += "    displayNetworks(data.networks);";
    html += "  }).catch(error => {";
    html += "    document.getElementById('networks').innerHTML = 'Error scanning networks';";
    html += "  });";
    html += "}";
    
    html += "function displayNetworks(networks) {";
    html += "  const container = document.getElementById('networks');";
    html += "  if (networks.length === 0) {";
    html += "    container.innerHTML = 'No networks found';";
    html += "    return;";
    html += "  }";
    html += "  let html = '';";
    html += "  networks.forEach(network => {";
    html += "    html += '<div class=\"network-item\" onclick=\"selectNetwork(\\'' + network.ssid + '\\')\">';";
    html += "    html += '<div>' + network.ssid + ' (' + network.rssi + ' dBm) ' + network.encryption + '</div>';";
    html += "    html += '</div>';";
    html += "  });";
    html += "  container.innerHTML = html;";
    html += "}";
    
    html += "function selectNetwork(ssid) {";
    html += "  document.getElementById('ssid').value = ssid;";
    html += "}";
    
    html += "function connectWiFi() {";
    html += "  const ssid = document.getElementById('ssid').value;";
    html += "  const password = document.getElementById('password').value;";
    html += "  if (!ssid) {";
    html += "    showStatus('wifiStatus', 'Please select a WiFi network', 'error');";
    html += "    return;";
    html += "  }";
    html += "  showStatus('wifiStatus', 'Connecting to network...', 'info');";
    html += "  fetch('/connect', {";
    html += "    method: 'POST',";
    html += "    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },";
    html += "    body: 'ssid=' + encodeURIComponent(ssid) + '&password=' + encodeURIComponent(password)";
    html += "  }).then(response => response.json()).then(data => {";
    html += "    if (data.success) {";
    html += "      showStatus('wifiStatus', 'Connected successfully! IP: ' + data.ip, 'success');";
    html += "      setTimeout(() => {";
    html += "        showStatus('generalStatus', 'Device setup complete! Restarting in 10 seconds...', 'success');";
    html += "        setTimeout(() => restartDevice(), 10000);";
    html += "      }, 2000);";
    html += "    } else {";
    html += "      showStatus('wifiStatus', 'Connection failed: ' + data.message, 'error');";
    html += "    }";
    html += "  }).catch(error => {";
    html += "    showStatus('wifiStatus', 'Connection error', 'error');";
    html += "  });";
    html += "}";
    
    html += "function checkStatus() {";
    html += "  fetch('/status').then(response => response.json()).then(data => {";
    html += "    let statusText = 'Device Status:<br>';";
    html += "    statusText += 'WiFi: ' + (data.wifi_connected ? 'Connected' : 'Disconnected') + '<br>';";
    html += "    statusText += 'Free Memory: ' + data.free_memory + ' bytes<br>';";
    html += "    statusText += 'Uptime: ' + data.uptime + ' seconds';";
    html += "    showStatus('generalStatus', statusText, 'info');";
    html += "  }).catch(error => {";
    html += "    showStatus('generalStatus', 'Error checking status', 'error');";
    html += "  });";
    html += "}";
    
    html += "function restartDevice() {";
    html += "  if (confirm('Are you sure you want to restart the device?')) {";
    html += "    showStatus('generalStatus', 'Restarting device...', 'info');";
    html += "    fetch('/restart', { method: 'POST' });";
    html += "  }";
    html += "}";
    
    html += "function showStatus(elementId, message, type) {";
    html += "  const element = document.getElementById(elementId);";
    html += "  element.innerHTML = '<div class=\"status ' + type + '\">' + message + '</div>';";
    html += "}";
    
    html += "window.onload = function() { setTimeout(scanNetworks, 1000); };";
    html += "</script>";
    
    html += "</body></html>";
    
    return html;
}

void handleNetworkScan() {
    Serial.println("Scanning for networks...");
    
    WiFi.mode(WIFI_AP_STA);
    int n = WiFi.scanNetworks();
    
    StaticJsonDocument<2048> doc;
    JsonArray networks = doc.createNestedArray("networks");
    
    for (int i = 0; i < n; i++) {
        JsonObject network = networks.createNestedObject();
        network["ssid"] = WiFi.SSID(i);
        network["rssi"] = WiFi.RSSI(i);
        network["encryption"] = getEncryptionType(WiFi.encryptionType(i));
    }
    
    String response;
    serializeJson(doc, response);
    
    portalServer.send(200, "application/json", response);
    
    // Return to AP+STA mode
    WiFi.mode(WIFI_AP_STA);
}

String getEncryptionType(wifi_auth_mode_t encryptionType) {
    switch (encryptionType) {
        case WIFI_AUTH_OPEN: return "Open";
        case WIFI_AUTH_WEP: return "WEP";
        case WIFI_AUTH_WPA_PSK: return "WPA";
        case WIFI_AUTH_WPA2_PSK: return "WPA2";
        case WIFI_AUTH_WPA_WPA2_PSK: return "WPA/WPA2";
        case WIFI_AUTH_WPA2_ENTERPRISE: return "WPA2-Enterprise";
        default: return "Unknown";
    }
}

void handleWiFiConnect() {
    // Handle form-encoded data from the web form
    String ssid = portalServer.arg("ssid");
    String password = portalServer.arg("password");
    
    if (ssid.length() == 0) {
        portalServer.send(400, "application/json", "{\"success\":false,\"message\":\"SSID is required\"}");
        return;
    }
    
    Serial.printf("Attempting to connect to: %s\n", ssid.c_str());
    
    // Switch to station mode and try to connect
    WiFi.mode(WIFI_AP_STA);
    WiFi.begin(ssid.c_str(), password.c_str());
    
    // Wait for connection (max 15 seconds)
    unsigned long startTime = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startTime < 15000) {
        delay(500);
        Serial.print(".");
        esp_task_wdt_reset();
        
        // Blink LED during connection attempt
        setLEDColor("yellow", 50);
        delay(100);
        clearLEDs();
        delay(100);
    }
    
    StaticJsonDocument<256> response;
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi connected successfully!");
        Serial.printf("IP Address: %s\n", WiFi.localIP().toString().c_str());
        
        // Save configuration using direct Preferences to match wifi_manager.cpp
        Preferences prefs;
        prefs.begin("wifi", false);
        prefs.putString("ssid", ssid);
        prefs.putString("password", password);
        prefs.end();
        
        Serial.println("✅ WiFi credentials saved to NVS");
        
        response["success"] = true;
        response["message"] = "Connected successfully";
        response["ip"] = WiFi.localIP().toString();
        
        configurationComplete = true;
        
        // Success LED indication
        setLEDColor("green", 100);
        
    } else {
        Serial.println("\nWiFi connection failed!");
        
        response["success"] = false;
        response["message"] = "Connection failed - check password";
        
        // Error LED indication
        setLEDColor("red", 100);
        delay(1000);
        setLEDColor("blue", 100); // Return to portal mode indication
        
        // Keep AP+STA so portal remains visible and STA can retry
        WiFi.mode(WIFI_AP_STA);
    }
    
    String responseStr;
    serializeJson(response, responseStr);
    portalServer.send(200, "application/json", responseStr);
}

void handleConnectionStatus() {
    StaticJsonDocument<512> doc;
    
    doc["wifi_connected"] = WiFi.status() == WL_CONNECTED;
    doc["ip_address"] = WiFi.localIP().toString();
    doc["free_memory"] = ESP.getFreeHeap();
    doc["uptime"] = millis() / 1000;
    doc["device_id"] = "teddy-001";
    doc["firmware_version"] = "1.0.0";
    doc["mac_address"] = WiFi.macAddress();
    
    String response;
    serializeJson(doc, response);
    
    portalServer.send(200, "application/json", response);
}

void handleDeviceConfig() {
    // Accept JSON body to update device configuration (local server, child info)
    if (portalServer.method() != HTTP_POST) {
        portalServer.send(405, "application/json", "{\"error\":\"Method Not Allowed\"}");
        return;
    }

    if (!portalServer.hasArg("plain")) {
        portalServer.send(400, "application/json", "{\"error\":\"Missing body\"}");
        return;
    }

    String body = portalServer.arg("plain");
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, body);
    if (err) {
        portalServer.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
        return;
    }

    extern ConfigManager configManager;
    TeddyConfig &cfg = configManager.getConfig();

    if (doc.containsKey("server_host")) {
        cfg.server_host = doc["server_host"].as<String>();
    }
    if (doc.containsKey("server_port")) {
        cfg.server_port = doc["server_port"].as<int>();
    }
    if (doc.containsKey("child_name")) {
        cfg.child_name = doc["child_name"].as<String>();
    }
    if (doc.containsKey("child_age")) {
        cfg.child_age = doc["child_age"].as<int>();
    }
    if (doc.containsKey("ssl_enabled")) {
        cfg.ssl_enabled = doc["ssl_enabled"].as<bool>();
    }

    configManager.saveConfiguration();

    StaticJsonDocument<256> resp;
    resp["success"] = true;
    resp["server_host"] = cfg.server_host;
    resp["server_port"] = cfg.server_port;
    String out;
    serializeJson(resp, out);
    portalServer.send(200, "application/json", out);
}

void handleRestart() {
    portalServer.send(200, "application/json", "{\"message\":\"Restarting device...\"}");
    delay(1000);
    ESP.restart();
}

void handleWiFiPortal() {
    if (!portalActive) return;
    
    // Handle DNS requests
    dnsServer.processNextRequest();
    
    // Handle web server requests
    portalServer.handleClient();
    
    // Check for timeout
    if (millis() - portalStartTime > PORTAL_TIMEOUT && !configurationComplete) {
        Serial.println("Portal timeout - stopping portal");
        stopWiFiPortal();
        return;
    }
    
    // Check if configuration is complete
    if (configurationComplete && WiFi.status() == WL_CONNECTED) {
        Serial.println("Configuration complete - stopping portal");
        delay(5000); // Give time for final web requests
        stopWiFiPortal();
        return;
    }
    
    // Portal status LED indication
    static unsigned long lastBlink = 0;
    if (millis() - lastBlink > 2000) {
        setLEDColor("blue", 50);
        delay(100);
        clearLEDs();
        lastBlink = millis();
    }
}

void stopWiFiPortal() {
    if (!portalActive) return;
    
    Serial.println("Stopping WiFi Portal...");
    
    portalServer.stop();
    dnsServer.stop();
    WiFi.softAPdisconnect(true);
    
    portalActive = false;
    
    // Switch to station mode if connected
    if (WiFi.status() == WL_CONNECTED) {
        WiFi.mode(WIFI_STA);
        Serial.println("Switched to Station mode");
        setLEDColor("green", 100);
        delay(1000);
        clearLEDs();
    } else {
        WiFi.mode(WIFI_OFF);
        Serial.println("WiFi turned off");
    }
}

bool isPortalActive() {
    return portalActive;
}

bool isConfigurationComplete() {
    return configurationComplete;
}

// Compatibility function called from main.cpp
void startConfigPortal() {
    startWiFiPortal();
}
