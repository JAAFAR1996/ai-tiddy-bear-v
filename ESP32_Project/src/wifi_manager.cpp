#include "wifi_manager.h"
#include "hardware.h"
#include "config.h"
#include <Preferences.h>
#include <WebServer.h>
#include <DNSServer.h>

WiFiManager wifiManager;
DeviceConfig deviceConfig;
Preferences preferences;
String wifiAPPassword = ""; // Will be generated at runtime
String deviceSecretKey = ""; // Will be generated at runtime

// Enhanced WiFi Management System
WebServer setupServer(80);
DNSServer dnsServer;
bool setupModeActive = false;
unsigned long setupModeStartTime = 0;
const unsigned long SETUP_MODE_TIMEOUT = 180000; // 3 minutes
const unsigned long WIFI_RETRY_TIMEOUT = 60000; // 1 minute
const unsigned long POWER_BUTTON_LONG_PRESS = 5000; // 5 seconds

// Enhanced connection monitoring
bool isConnectedToInternet = false;
unsigned long lastInternetCheck = 0;
const unsigned long INTERNET_CHECK_INTERVAL = 60000; // Check every minute
unsigned long lastDisconnectionAlert = 0;
const unsigned long DISCONNECTION_ALERT_INTERVAL = 30000; // 30 seconds between alerts

// Custom parameters for device configuration
WiFiManagerParameter custom_server_host("server", "Server Host", "", 64);
WiFiManagerParameter custom_server_port("port", "Server Port", "8005", 6);
WiFiManagerParameter custom_device_id("device_id", "Device ID", "", 32);
WiFiManagerParameter custom_device_secret("secret", "Device Secret", "", 64);
WiFiManagerParameter custom_child_id("child_id", "Child ID", "", 32);
WiFiManagerParameter custom_child_name("child_name", "Child Name", "", 32);
WiFiManagerParameter custom_child_age("child_age", "Child Age", "7", 3);

bool shouldSaveConfig = false;
bool waitingForConnection = false;
unsigned long connectionStartTime = 0;

bool initWiFiManager() {
  Serial.println("🌐 Initializing WiFi Manager...");
  
  // Generate secure WiFi AP password
  generateWiFiAPPassword();
  
  // Generate secure device secret key
  generateDeviceSecretKey();
  
  // Initialize preferences
  preferences.begin("teddy-config", false);
  
  // Load existing configuration
  deviceConfig = loadDeviceConfig();
  
  // Set custom parameters with loaded values
  custom_server_host.setValue(deviceConfig.server_host, 64);
  
  char port_str[6];
  sprintf(port_str, "%d", deviceConfig.server_port);
  custom_server_port.setValue(port_str, 6);
  
  custom_device_id.setValue(deviceConfig.device_id, 32);
  custom_device_secret.setValue(deviceConfig.device_secret, 64);
  custom_child_id.setValue(deviceConfig.child_id, 32);
  custom_child_name.setValue(deviceConfig.child_name, 32);
  
  char age_str[3];
  sprintf(age_str, "%d", deviceConfig.child_age);
  custom_child_age.setValue(age_str, 3);
  
  // Add custom parameters
  wifiManager.addParameter(&custom_server_host);
  wifiManager.addParameter(&custom_server_port);
  wifiManager.addParameter(&custom_device_id);
  wifiManager.addParameter(&custom_device_secret);
  wifiManager.addParameter(&custom_child_id);
  wifiManager.addParameter(&custom_child_name);
  wifiManager.addParameter(&custom_child_age);
  
  // Set callback for saving config
  wifiManager.setSaveConfigCallback(saveConfigCallback);
  
  // Configure WiFi Manager
  wifiManager.setConfigPortalTimeout(WIFI_CONFIG_TIMEOUT);
  wifiManager.setAPCallback([](WiFiManager *myWiFiManager) {
    Serial.println("🔧 Entered config mode");
    Serial.print("AP IP address: ");
    Serial.println(WiFi.softAPIP());
    
    // Show config mode on LEDs
    setLEDColor("blue", 100);
    delay(500);
    setLEDColor("white", 50);
  });
  
  return true;
}

bool connectToWiFi() {
  Serial.println("📡 Starting Enhanced WiFi Connection...");
  
  // Load saved networks
  deviceConfig = loadDeviceConfig();
  
  if (deviceConfig.configured && strlen(deviceConfig.server_host) > 0) {
    Serial.println("🔗 Attempting to connect with saved credentials...");
    
    // Set waiting state
    waitingForConnection = true;
    connectionStartTime = millis();
    
    // Show connection attempt animation
    playConnectingAnimation();
    
    // Try auto-connect with saved credentials
    WiFi.mode(WIFI_STA);
    
    Serial.println("⏳ Trying to connect for 1 minute...");
    unsigned long startTime = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startTime < WIFI_RETRY_TIMEOUT) {
      delay(500);
      Serial.print(".");
      
      // Blink LED during connection
      setLEDColor("blue", 50);
      delay(250);
      setLEDColor("off", 0);
      delay(250);
      
      // Check for power button long press during wait
      if (checkPowerButtonLongPress()) {
        Serial.println("\n🔧 Power button long press detected during connection!");
        return startSmartSetupMode();
      }
    }
    
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\n✅ Connected to saved WiFi network!");
      
      // Test internet connection
      if (testInternetConnection()) {
        Serial.println("🌐 Internet connection verified!");
        isConnectedToInternet = true;
        playSuccessAnimation();
        waitingForConnection = false;
        return true;
      } else {
        Serial.println("⚠️ WiFi connected but no internet access");
        isConnectedToInternet = false;
        playWarningAnimation();
        // Continue monitoring for internet
        startConnectionMonitoring();
        return true; // Still return true as WiFi is connected
      }
    } else {
      Serial.println("\n❌ Failed to connect to any saved network after 1 minute");
      playFailureAnimation();
      
      // Enter waiting mode for manual setup
      enterWaitingMode();
      return false;
    }
  } else {
    Serial.println("🆕 No saved configuration found");
    enterWaitingMode();
    return false;
  }
}

void enterWaitingMode() {
  Serial.println("⏳ Entering enhanced waiting mode...");
  waitingForConnection = true;
  
  // Play waiting mode animation (lights only, no sound)
  playWaitingModeAnimation();
  
  // Voice instruction (one time only)
  Serial.println("🎵 Voice instruction: اضغط زر الباور لمدة 5 ثوانٍ لإعداد الواي فاي");
  playVoiceInstruction("press_power_button_setup");
  
  Serial.println("💡 Waiting mode: Slow blue pulse, power button monitoring active");
  Serial.println("🔘 Press power button for 5-7 seconds to start WiFi setup");
  
  // Enhanced waiting loop with power button monitoring
  while (waitingForConnection) {
    // Slow pulsing blue LED (breathing effect)
    for (int i = 0; i < 255; i += 3) {
      setLEDColor("blue", i);
      delay(15);
      
      if (checkPowerButtonLongPress()) {
        Serial.println("🚀 Exiting waiting mode - starting setup!");
        waitingForConnection = false;
        startSmartSetupMode();
        return;
      }
    }
    
    for (int i = 255; i > 0; i -= 3) {
      setLEDColor("blue", i);
      delay(15);
      
      if (checkPowerButtonLongPress()) {
        Serial.println("🚀 Exiting waiting mode - starting setup!");
        waitingForConnection = false;
        startSmartSetupMode();
        return;
      }
    }
    
    // Brief pause between breathing cycles
    delay(500);
  }
}

bool checkPowerButtonLongPress() {
  static unsigned long buttonPressStart = 0;
  static bool buttonPressed = false;
  static bool feedbackGiven = false;
  
  if (digitalRead(BUTTON_PIN) == LOW && !buttonPressed) {
    // Button just pressed
    buttonPressed = true;
    feedbackGiven = false;
    buttonPressStart = millis();
    Serial.println("🔘 Power button pressed - monitoring for long press...");
    
    // Immediate visual feedback
    setLEDColor("yellow", 100);
    delay(50);
    setLEDColor("off", 0);
    
  } else if (digitalRead(BUTTON_PIN) == HIGH && buttonPressed) {
    // Button released
    buttonPressed = false;
    feedbackGiven = false;
    unsigned long pressDuration = millis() - buttonPressStart;
    
    if (pressDuration >= POWER_BUTTON_LONG_PRESS) {
      Serial.printf("✅ Long press completed: %lu ms\n", pressDuration);
      return true;
    } else {
      Serial.printf("⏱️ Short press: %lu ms (need %lu ms for setup)\n", pressDuration, POWER_BUTTON_LONG_PRESS);
      
      // Short press feedback
      setLEDColor("orange", 50);
      delay(200);
      setLEDColor("off", 0);
    }
  } else if (buttonPressed && !feedbackGiven && millis() - buttonPressStart >= POWER_BUTTON_LONG_PRESS) {
    // Long press threshold reached while still holding
    Serial.println("🎯 Long press threshold reached - giving immediate feedback!");
    feedbackGiven = true;
    
    // Immediate confirmation feedback (sound + light)
    playLongPressConfirmation();
    
    // Continue holding verification
    Serial.println("⏰ Continue holding to activate setup mode...");
    
  } else if (buttonPressed && feedbackGiven && millis() - buttonPressStart >= (POWER_BUTTON_LONG_PRESS + 1000)) {
    // Extra second held after feedback - activate setup
    Serial.println("🚀 Setup mode activation confirmed!");
    buttonPressed = false;
    feedbackGiven = false;
    return true;
  }
  
  return false;
}

bool startSmartSetupMode() {
  Serial.println("🚀 Starting Enhanced Smart Setup Mode!");
  
  // Immediate confirmation feedback (sound + light)
  playSetupModeStartSound();
  playSetupConfirmationAnimation();
  
  // Voice instruction with countdown
  Serial.println("🎵 Voice: الرجاء الاتصال بشبكة AI-TEDDY-SETUP وإعداد الواي فاي خلال 3 دقائق");
  playVoiceInstruction("connect_to_setup_network");
  
  setupModeActive = true;
  setupModeStartTime = millis();
  
  // Stop any existing WiFi connection
  WiFi.disconnect();
  delay(100);
  
  // Start Soft-AP mode (without password for easy access)
  WiFi.mode(WIFI_AP);
  
  // Create temporary network - unique name with timestamp
  String apName = "AI-TEDDY-SETUP";
  bool apStarted = WiFi.softAP(apName.c_str(), wifiAPPassword.c_str()); // Secure password
  
  if (!apStarted) {
    Serial.println("❌ Failed to start setup access point");
    playErrorAnimation();
    playVoiceInstruction("setup_failed");
    return false;
  }
  
  // Configure static IP for captive portal
  IPAddress local_ip(192, 168, 4, 1);
  IPAddress gateway(192, 168, 4, 1);
  IPAddress subnet(255, 255, 255, 0);
  WiFi.softAPConfig(local_ip, gateway, subnet);
  
  Serial.printf("✅ Setup network created successfully!\n");
  Serial.printf("📱 Network Name: %s\n", apName.c_str());
  Serial.printf("🌐 Setup Page: http://192.168.4.1\n");
  Serial.printf("🔐 WiFi Password: %s\n", wifiAPPassword.c_str());
  Serial.printf("⏰ Active for 3 minutes only\n");
  
  // Start DNS server for captive portal redirection
  dnsServer.start(53, "*", local_ip);
  
  // Setup web server routes for configuration
  setupWebServerRoutes();
  setupServer.begin();
  
  // Start setup mode monitoring and animations
  startSetupModeMonitoring();
  
  Serial.println("🎯 Smart setup mode is now active!");
  Serial.println("🔧 Users can now connect and configure WiFi");
  
  return true;
}

void setupWebServerRoutes() {
  // Main setup page (captive portal)
  setupServer.on("/", HTTP_GET, []() {
    String html = getSetupPageHTML();
    setupServer.send(200, "text/html", html);
  });
  
  // Handle captive portal requests
  setupServer.on("/generate_204", HTTP_GET, []() {
    String html = getSetupPageHTML();
    setupServer.send(200, "text/html", html);
  });
  
  setupServer.on("/fwlink", HTTP_GET, []() {
    String html = getSetupPageHTML();
    setupServer.send(200, "text/html", html);
  });
  
  // WiFi scan endpoint
  setupServer.on("/scan", HTTP_GET, []() {
    String json = scanWiFiNetworks();
    setupServer.send(200, "application/json", json);
  });
  
  // WiFi connection endpoint
  setupServer.on("/connect", HTTP_POST, []() {
    String ssid = setupServer.arg("ssid");
    String password = setupServer.arg("password");
    
    if (ssid.length() > 0) {
      Serial.printf("🔗 Attempting to connect to new network: %s\n", ssid.c_str());
      
      // Visual feedback during connection attempt
      playConnectingToNewNetworkAnimation();
      
      if (connectToNewNetwork(ssid, password)) {
        // Success response
        setupServer.send(200, "application/json", 
          "{\"status\":\"success\",\"message\":\"تم ربط الدمية بنجاح! 🎉\"}");
        
        Serial.println("✅ Successfully connected to new network!");
        
        // Success feedback (sound + light)
        playSuccessAnimation();
        playVoiceInstruction("connection_success");
        
        // Auto-close setup mode after successful connection
        delay(3000); // Give time for user to see success message
        closeSetupMode();
      } else {
        // Error response
        setupServer.send(400, "application/json", 
          "{\"status\":\"error\",\"message\":\"فشل في الاتصال بالشبكة - تحقق من كلمة المرور\"}");
          
        Serial.println("❌ Failed to connect to new network");
        playErrorAnimation();
      }
    } else {
      setupServer.send(400, "application/json", 
        "{\"status\":\"error\",\"message\":\"اسم الشبكة مطلوب\"}");
    }
  });
  
  // Status endpoint with enhanced information
  setupServer.on("/status", HTTP_GET, []() {
    unsigned long timeLeft = 0;
    if (millis() - setupModeStartTime < SETUP_MODE_TIMEOUT) {
      timeLeft = SETUP_MODE_TIMEOUT - (millis() - setupModeStartTime);
    }
    
    String json = "{";
    json += "\"timeLeft\":" + String(timeLeft / 1000) + ",";
    json += "\"connected\":" + (WiFi.status() == WL_CONNECTED ? "true" : "false") + ",";
    json += "\"setupMode\":" + (setupModeActive ? "true" : "false") + ",";
    json += "\"deviceName\":\"AI Teddy Bear\",";
    json += "\"version\":\"2.0\"";
    json += "}";
    
    setupServer.send(200, "application/json", json);
  });
}
}

String getSetupPageHTML() {
  return R"(<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧸 إعداد الدب الذكي</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            color: white;
            text-align: center;
        }
        .container {
            max-width: 400px;
            margin: 0 auto;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 30px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        h1 { margin-bottom: 30px; font-size: 24px; }
        .teddy { font-size: 48px; margin-bottom: 20px; }
        .form-group {
            margin-bottom: 20px;
            text-align: right;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        select, input {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            background: rgba(255,255,255,0.9);
            color: #333;
            box-sizing: border-box;
        }
        button {
            background: #28a745;
            color: white;
            padding: 15px 30px;
            border: none;
            border-radius: 8px;
            font-size: 18px;
            cursor: pointer;
            width: 100%;
            margin-top: 20px;
            transition: background 0.3s;
        }
        button:hover { background: #218838; }
        button:disabled {
            background: #6c757d;
            cursor: not-allowed;
        }
        .timer {
            background: rgba(255,255,255,0.2);
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .status {
            padding: 10px;
            border-radius: 8px;
            margin-top: 20px;
            font-weight: bold;
        }
        .success { background: rgba(40,167,69,0.8); }
        .error { background: rgba(220,53,69,0.8); }
        .loading {
            display: none;
            margin-top: 10px;
        }
        .spinner {
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top: 3px solid white;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="teddy">🧸</div>
        <h1>إعداد الدب الذكي</h1>
        
        <div class="timer" id="timer">
            الوقت المتبقي: <span id="timeLeft">3:00</span>
        </div>
        
        <form id="wifiForm">
            <div class="form-group">
                <label for="ssid">اختر شبكة WiFi:</label>
                <select id="ssid" required>
                    <option value="">جاري البحث عن الشبكات...</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="password">كلمة المرور:</label>
                <input type="password" id="password" placeholder="أدخل كلمة مرور الشبكة">
            </div>
            
            <button type="submit" id="connectBtn">
                🔗 ربط الدمية بالشبكة
            </button>
        </form>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>جاري الاتصال بالشبكة...</p>
        </div>
        
        <div id="status"></div>
    </div>

    <script>
        let timeLeft = 180; // 3 minutes
        
        // Update timer
        function updateTimer() {
            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            document.getElementById('timeLeft').textContent = 
                minutes + ':' + (seconds < 10 ? '0' : '') + seconds;
            
            if (timeLeft <= 0) {
                showStatus('انتهى الوقت المحدد. يرجى إعادة المحاولة.', 'error');
                document.getElementById('connectBtn').disabled = true;
                return;
            }
            
            timeLeft--;
            setTimeout(updateTimer, 1000);
        }
        
        // Load WiFi networks
        function loadNetworks() {
            fetch('/scan')
                .then(response => response.json())
                .then(networks => {
                    const select = document.getElementById('ssid');
                    select.innerHTML = '<option value="">اختر شبكة...</option>';
                    
                    networks.forEach(network => {
                        const option = document.createElement('option');
                        option.value = network.ssid;
                        option.textContent = network.ssid + ' (' + network.rssi + 'dBm)';
                        select.appendChild(option);
                    });
                })
                .catch(err => {
                    console.error('Error loading networks:', err);
                    document.getElementById('ssid').innerHTML = 
                        '<option value="">خطأ في تحميل الشبكات</option>';
                });
        }
        
        // Handle form submission
        document.getElementById('wifiForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const ssid = document.getElementById('ssid').value;
            const password = document.getElementById('password').value;
            
            if (!ssid) {
                showStatus('يرجى اختيار شبكة WiFi', 'error');
                return;
            }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('connectBtn').disabled = true;
            
            // Send connection request
            fetch('/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'ssid=' + encodeURIComponent(ssid) + '&password=' + encodeURIComponent(password)
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('loading').style.display = 'none';
                
                if (data.status === 'success') {
                    showStatus('✅ ' + data.message, 'success');
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } else {
                    showStatus('❌ ' + data.message, 'error');
                    document.getElementById('connectBtn').disabled = false;
                }
            })
            .catch(err => {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('connectBtn').disabled = false;
                showStatus('❌ خطأ في الاتصال', 'error');
            });
        });
        
        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = 'status ' + type;
            status.style.display = 'block';
        }
        
        // Initialize
        updateTimer();
        loadNetworks();
        
        // Refresh networks every 10 seconds
        setInterval(loadNetworks, 10000);
    </script>
</body>
</html>)";
}

String scanWiFiNetworks() {
  Serial.println("🔍 Scanning for WiFi networks...");
  
  int networkCount = WiFi.scanNetworks();
  String json = "[";
  
  for (int i = 0; i < networkCount; i++) {
    if (i > 0) json += ",";
    json += "{";
    json += "\"ssid\":\"" + WiFi.SSID(i) + "\",";
    json += "\"rssi\":" + String(WiFi.RSSI(i)) + ",";
    json += "\"encryption\":" + String(WiFi.encryptionType(i));
    json += "}";
  }
  
  json += "]";
  WiFi.scanDelete();
  
  return json;
}

bool connectToNewNetwork(String ssid, String password) {
  Serial.printf("🔗 Connecting to new network: %s\n", ssid.c_str());
  
  // Disconnect from AP mode
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid.c_str(), password.c_str());
  
  // Wait for connection with timeout
  unsigned long startTime = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startTime < 15000) {
    delay(500);
    Serial.print(".");
    
    // Show connecting animation
    setLEDColor("orange", 100);
    delay(250);
    setLEDColor("off", 0);
    delay(250);
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ Successfully connected to new network!");
    Serial.printf("📍 IP Address: %s\n", WiFi.localIP().toString().c_str());
    
    // Save new network to preferences
    saveNewNetworkCredentials(ssid, password);
    
    // Success feedback
    playSuccessAnimation();
    
    return true;
  } else {
    Serial.println("\n❌ Failed to connect to new network");
    playErrorAnimation();
    return false;
  }
}

void saveNewNetworkCredentials(String ssid, String password) {
  Serial.println("💾 Saving new network credentials...");
  
  preferences.putString("wifi_ssid", ssid);
  preferences.putString("wifi_password", password);
  preferences.putBool("wifi_configured", true);
  
  Serial.println("✅ Network credentials saved!");
}

void closeSetupMode() {
  Serial.println("🔚 Closing setup mode...");
  
  setupModeActive = false;
  
  // Stop servers
  setupServer.stop();
  dnsServer.stop();
  
  // Close AP mode
  WiFi.softAPdisconnect(true);
  
  // Success feedback
  playSetupCompleteAnimation();
  
  Serial.println("✅ Setup mode closed successfully!");
}
  
  if (result) {
    Serial.println("✅ WiFi connected successfully!");
    
    // Save configuration if needed
    if (shouldSaveConfig) {
      saveDeviceConfig(deviceConfig);
    }
    
    playSuccessAnimation();
  } else {
    Serial.println("❌ Failed to connect to WiFi");
    playErrorAnimation();
  }
  
  return result;
}

void saveConfigCallback() {
  Serial.println("💾 Should save config");
  shouldSaveConfig = true;
  
  // Update device config with new values
  strncpy(deviceConfig.server_host, custom_server_host.getValue(), 64);
  deviceConfig.server_port = atoi(custom_server_port.getValue());
  strncpy(deviceConfig.device_id, custom_device_id.getValue(), 32);
  strncpy(deviceConfig.device_secret, custom_device_secret.getValue(), 64);
  strncpy(deviceConfig.child_id, custom_child_id.getValue(), 32);
  strncpy(deviceConfig.child_name, custom_child_name.getValue(), 32);
  deviceConfig.child_age = atoi(custom_child_age.getValue());
  deviceConfig.ssl_enabled = USE_SSL;
  deviceConfig.configured = true;
}

bool saveDeviceConfig(const DeviceConfig& config) {
  Serial.println("💾 Saving device configuration...");
  
  preferences.putString("server_host", config.server_host);
  preferences.putInt("server_port", config.server_port);
  preferences.putString("device_id", config.device_id);
  preferences.putString("device_secret", config.device_secret);
  preferences.putString("child_id", config.child_id);
  preferences.putString("child_name", config.child_name);
  preferences.putInt("child_age", config.child_age);
  preferences.putBool("ssl_enabled", config.ssl_enabled);
  preferences.putBool("configured", config.configured);
  
  Serial.println("✅ Configuration saved successfully!");
  return true;
}

DeviceConfig loadDeviceConfig() {
  DeviceConfig config = {};
  
  Serial.println("📖 Loading device configuration...");
  
  // Load from preferences with production defaults
  String server_host = preferences.getString("server_host", DEFAULT_SERVER_HOST);
  strncpy(config.server_host, server_host.c_str(), 64);
  
  config.server_port = preferences.getInt("server_port", DEFAULT_SERVER_PORT);
  
  String device_id = preferences.getString("device_id", "");
  strncpy(config.device_id, device_id.c_str(), 32);
  
  String device_secret = preferences.getString("device_secret", "");
  strncpy(config.device_secret, device_secret.c_str(), 64);
  
  String child_id = preferences.getString("child_id", "");
  strncpy(config.child_id, child_id.c_str(), 32);
  
  String child_name = preferences.getString("child_name", "");
  strncpy(config.child_name, child_name.c_str(), 32);
  
  config.child_age = preferences.getInt("child_age", 7);
  config.ssl_enabled = preferences.getBool("ssl_enabled", USE_SSL);
  config.configured = preferences.getBool("configured", false);
  
  Serial.printf("📋 Loaded config: Host=%s, Port=%d, Configured=%s\n", 
                config.server_host, config.server_port, 
                config.configured ? "Yes" : "No");
  
  return config;
}

void handleSetupMode() {
  if (!setupModeActive) return;
  
  // Handle DNS requests for captive portal
  dnsServer.processNextRequest();
  
  // Handle HTTP requests
  setupServer.handleClient();
  
  // Check timeout
  if (millis() - setupModeStartTime > SETUP_MODE_TIMEOUT) {
    Serial.println("⏰ Setup mode timeout reached");
    
    // Play timeout sound
    playTimeoutAnimation();
    
    // Close setup mode
    closeSetupMode();
    
    // Return to waiting mode
    enterWaitingMode();
  }
  
  // Show countdown animation
  static unsigned long lastCountdownUpdate = 0;
  if (millis() - lastCountdownUpdate > 10000) { // Every 10 seconds
    unsigned long timeLeft = SETUP_MODE_TIMEOUT - (millis() - setupModeStartTime);
    Serial.printf("⏱️ Setup mode time left: %lu seconds\n", timeLeft / 1000);
    
    // Voice reminder every 30 seconds
    if (timeLeft <= 120000 && timeLeft > 110000) { // 2 minutes left
      Serial.println("🎵 Voice: 2 minutes remaining to configure WiFi");
    } else if (timeLeft <= 60000 && timeLeft > 50000) { // 1 minute left
      Serial.println("🎵 Voice: 1 minute remaining to configure WiFi");
    } else if (timeLeft <= 30000 && timeLeft > 20000) { // 30 seconds left
      Serial.println("🎵 Voice: 30 seconds remaining");
    }
    
    lastCountdownUpdate = millis();
  }
}
  
  // Restart device
  delay(2000);
  ESP.restart();
}

bool isConfigured() {
  return deviceConfig.configured && 
         strlen(deviceConfig.server_host) > 0 && 
         strlen(deviceConfig.device_id) > 0;
}

String getDeviceInfo() {
  StaticJsonDocument<512> doc;
  
  doc["device_id"] = deviceConfig.device_id;
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["chip_model"] = ESP.getChipModel();
  doc["free_heap"] = ESP.getFreeHeap();
  doc["mac_address"] = WiFi.macAddress();
  doc["wifi_ssid"] = WiFi.SSID();
  doc["wifi_rssi"] = WiFi.RSSI();
  doc["server_host"] = deviceConfig.server_host;
  doc["server_port"] = deviceConfig.server_port;
  doc["child_id"] = deviceConfig.child_id;
  doc["child_name"] = deviceConfig.child_name;
  doc["child_age"] = deviceConfig.child_age;
  doc["uptime"] = millis() / 1000;
  
  String output;
  serializeJson(doc, output);
  return output;
}

// Animation functions for setup process
void playSetupAnimation() {
  // Blue pulsing for setup mode
  for (int i = 0; i < 3; i++) {
    setLEDColor("blue", 100);
    delay(300);
    setLEDColor("blue", 20);
    delay(300);
  }
}

void playSuccessAnimation() {
  // Green wave for success
  for (int i = 0; i < NUM_LEDS; i++) {
    setLEDIndex(i, "green", 100);
    delay(100);
  }
  delay(500);
  clearLEDs();
}

void playErrorAnimation() {
  // Red flash for error
  for (int i = 0; i < 5; i++) {
    setLEDColor("red", 100);
    delay(200);
    clearLEDs();
    delay(200);
  }
}

void playResetAnimation() {
  // Rainbow for reset
  const char* colors[] = {"red", "orange", "yellow", "green", "blue", "purple"};
  for (int cycle = 0; cycle < 2; cycle++) {
    for (int i = 0; i < 6; i++) {
      setLEDColor(colors[i], 80);
      delay(200);
    }
  }
  clearLEDs();
}

// New WiFi management functions
bool testInternetConnection() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  
  Serial.println("🌐 Testing internet connection...");
  
  // Test with multiple servers for reliability
  const char* testServers[] = {
    "8.8.8.8",      // Google DNS
    "1.1.1.1",      // Cloudflare DNS
    "208.67.222.222" // OpenDNS
  };
  
  WiFiClient client;
  
  for (int i = 0; i < 3; i++) {
    Serial.printf("Testing server %s...\n", testServers[i]);
    
    if (client.connect(testServers[i], 53, 3000)) { // 3 second timeout
      client.stop();
      Serial.println("✅ Internet connection confirmed");
      return true;
    }
    delay(1000);
  }
  
  Serial.println("❌ No internet connection");
  return false;
}

void startConnectionMonitoring() {
  Serial.println("🔍 Starting connection monitoring...");
  
  // Reset monitoring variables
  isConnectedToInternet = testInternetConnection();
  lastInternetCheck = millis();
  
  if (isConnectedToInternet) {
    Serial.println("✅ Initial internet test passed");
    setLEDColor("green", 50);
    delay(1000);
    clearLEDs();
  } else {
    Serial.println("⚠️ Initial internet test failed");
    setLEDColor("orange", 50);
    delay(1000);
    clearLEDs();
  }
}

void playVoiceInstruction(const String& instruction) {
  Serial.printf("🎵 Voice instruction: %s\n", instruction.c_str());
  
  // Add visual feedback during voice instruction
  if (instruction.indexOf("WiFi") >= 0) {
    setLEDColor("blue", 30);
  } else if (instruction.indexOf("setup") >= 0) {
    setLEDColor("cyan", 30);
  } else if (instruction.indexOf("connect") >= 0) {
    setLEDColor("purple", 30);
  } else {
    setLEDColor("white", 20);
  }
  
  delay(2000); // Simulate voice duration
  clearLEDs();
}

void startSetupModeMonitoring() {
  if (!setupModeActive) return;
  
  Serial.println("👁️ Starting setup mode monitoring...");
  
  // Monitor for successful configuration
  static unsigned long lastStatusCheck = 0;
  
  if (millis() - lastStatusCheck > 5000) { // Check every 5 seconds
    lastStatusCheck = millis();
    
    // Check if WiFi credentials were entered
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("🎉 WiFi connection successful during setup!");
      
      // Test internet connection
      if (testInternetConnection()) {
        Serial.println("✅ Internet connection confirmed - closing setup mode");
        
        // Play success animation
        playSuccessAnimation();
        
        // Close setup mode
        closeSetupMode();
        
        // Start normal operation
        startConnectionMonitoring();
        return;
      }
    }
    
    // Show setup mode progress
    unsigned long timeLeft = SETUP_MODE_TIMEOUT - (millis() - setupModeStartTime);
    if (timeLeft > 0) {
      Serial.printf("⏱️ Setup mode: %lu seconds remaining\n", timeLeft / 1000);
      
      // Gentle blue pulse to indicate setup mode is active
      setLEDColor("blue", 20);
      delay(100);
      clearLEDs();
    }
  }
}

void handleInternetDisconnection() {
  static unsigned long lastDisconnectionAlert = 0;
  static bool alertActive = false;
  
  // Check internet connection every minute
  if (millis() - lastInternetCheck > INTERNET_CHECK_INTERVAL) {
    lastInternetCheck = millis();
    
    bool currentStatus = testInternetConnection();
    
    // Internet disconnected
    if (isConnectedToInternet && !currentStatus) {
      Serial.println("❌ Internet disconnection detected!");
      isConnectedToInternet = false;
      lastDisconnectionAlert = millis();
      alertActive = true;
      
      // Start immediate alert sequence
      for (int i = 0; i < 5; i++) {
        setLEDColor("red", 80);
        delay(200);
        clearLEDs();
        delay(200);
      }
    }
    // Internet reconnected
    else if (!isConnectedToInternet && currentStatus) {
      Serial.println("✅ Internet connection restored!");
      isConnectedToInternet = true;
      alertActive = false;
      
      // Success animation
      playSuccessAnimation();
    }
    else {
      isConnectedToInternet = currentStatus;
    }
  }
  
  // Handle disconnection alerts (every 30 seconds)
  if (alertActive && !isConnectedToInternet) {
    if (millis() - lastDisconnectionAlert > DISCONNECTION_ALERT_INTERVAL) {
      lastDisconnectionAlert = millis();
      
      Serial.println("🚨 Disconnection alert: Blinking 5 times");
      
      // 5 red blinks as requested (no sound)
      for (int i = 0; i < 5; i++) {
        setLEDColor("red", 100);
        delay(300);
        clearLEDs();
        delay(300);
      }
    }
  }
}

void generateWiFiAPPassword() {
  Serial.println("🔐 Generating secure WiFi AP password...");
  
  preferences.begin("wifi-ap", false);
  
  // Check if password already exists
  wifiAPPassword = preferences.getString("ap_password", "");
  
  if (wifiAPPassword.isEmpty()) {
    // Generate secure random password
    const char charset[] = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    const int passwordLength = 12;
    
    wifiAPPassword = "";
    for (int i = 0; i < passwordLength; i++) {
      int randomIndex = esp_random() % (sizeof(charset) - 1);
      wifiAPPassword += charset[randomIndex];
    }
    
    // Store password securely
    preferences.putString("ap_password", wifiAPPassword);
    Serial.printf("✅ New WiFi AP password generated: %s\n", wifiAPPassword.c_str());
  } else {
    Serial.println("✅ Using existing WiFi AP password");
  }
  
  preferences.end();
}

void generateDeviceSecretKey() {
  Serial.println("🔐 Generating secure device secret key...");
  
  preferences.begin("device-sec", false);
  
  // Check if secret key already exists
  deviceSecretKey = preferences.getString("secret_key", "");
  
  if (deviceSecretKey.isEmpty()) {
    // Generate secure random 32-character secret key
    const char charset[] = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    const int keyLength = 32;
    
    deviceSecretKey = "";
    for (int i = 0; i < keyLength; i++) {
      int randomIndex = esp_random() % (sizeof(charset) - 1);
      deviceSecretKey += charset[randomIndex];
    }
    
    // Store secret key securely
    preferences.putString("secret_key", deviceSecretKey);
    Serial.println("✅ New device secret key generated and stored");
  } else {
    Serial.println("✅ Using existing device secret key");
  }
  
  preferences.end();
}
