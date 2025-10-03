/*
🧸 AI TEDDY BEAR ESP32 - PRODUCTION CONTROLLER
============================================
Production-ready ESP32 with full management features
*/
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "config.h"
#include "hardware.h"
#include "websocket_handler.h"
#include "sensors.h"
#include "audio_handler.h"
#include "wifi_manager.h"
#include "wifi_portal.h"
#include "ota_manager.h"
#include "monitoring.h"
#include "security.h"
#include "device_management.h"
#include "device_id_manager.h"  // for getCurrentDeviceId()
#include "system_monitor.h"
#include "comprehensive_logging.h"  // Comprehensive logging system
#include "esp_heap_caps.h"
#include "esp_task_wdt.h"
#include <Preferences.h>
#include <Arduino.h> // for setCpuFrequencyMhz

// Production configuration
String deviceId = DEVICE_ID;

// Production system state
// Reflect build-time environment: 1 in production, 0 in local/dev
bool productionMode = PRODUCTION_MODE;
unsigned long systemStartTime = 0;

// Forward declarations
void initProductionSystems();
void handleProductionLoop();
void handleButton();
void printSystemInfo();
void performStartupChecks();
bool waitForInternet(unsigned long timeoutMs = 0);

// Timing variables
unsigned long lastHeartbeat = 0;
unsigned long lastButtonPress = 0;
unsigned long lastSystemCheck = 0;

void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.flush();
  logSystemEvent("System Starting", "AI Teddy Bear ESP32 - Production Starting");
  logSystemEvent("Firmware Version", FIRMWARE_VERSION);
  
  // Print initial heap status before initialization
  Serial.printf("💾 Initial heap: free=%u KB, largest=%u KB\n",
    heap_caps_get_free_size(MALLOC_CAP_8BIT) / 1024,
    heap_caps_get_largest_free_block(MALLOC_CAP_8BIT) / 1024);
    
  // Soft-start CPU to reduce inrush current on weak supplies
  setCpuFrequencyMhz(80);
  delay(100);
    
  systemStartTime = millis();
  
  // Extend WDT timeout for production safety (20s)
  esp_task_wdt_deinit();
  esp_task_wdt_init(20, true); // 20 second timeout
  esp_task_wdt_add(NULL); // Add current task
  
  // Initialize all production systems with WDT feeding
  initProductionSystems();
  
  // Feed WDT after initialization
  esp_task_wdt_reset();
  
  Serial.println("✅ ESP32 AI Teddy Bear Production Ready!");
  printSystemInfo();
}

void loop() {
  // Feed WDT regularly in main loop
  esp_task_wdt_reset();
  
  // Handle production systems
  handleProductionLoop();
  
  // Handle button with debouncing
  handleButton();
  
  // Handle WiFi management and internet monitoring
  handleInternetDisconnection();
  
  // Handle setup mode if active
  handleSetupMode();
  
  // Perform periodic system checks
  if (millis() - lastSystemCheck > SYSTEM_CHECK_INTERVAL) {
    performStartupChecks();
    lastSystemCheck = millis();
    
    // Print heap status during system check
    Serial.printf("💾 Heap: free=%u KB, largest=%u KB\n",
      heap_caps_get_free_size(MALLOC_CAP_8BIT) / 1024,
      heap_caps_get_largest_free_block(MALLOC_CAP_8BIT) / 1024);
  }
  
  // Send heartbeat
  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
    sendHeartbeat();
    lastHeartbeat = millis();
  }
  
  // Update LEDs - FastLED removed for I2S compatibility
  
  // Feed WDT before delay
  esp_task_wdt_reset();
  delay(10);
}

void initProductionSystems() {
  Serial.println("🔧 Initializing production systems...");
  
  // Initialize hardware first
  initHardware();
  
  // Boot-time override: hold button 3s to force setup portal and clear WiFi
  {
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    if (digitalRead(BUTTON_PIN) == LOW) {
      unsigned long holdStart = millis();
      while (digitalRead(BUTTON_PIN) == LOW && (millis() - holdStart) < 3000) {
        delay(10);
      }
      if ((millis() - holdStart) >= 3000) {
        Serial.println("🧽 Clearing saved WiFi credentials and starting setup portal...");
        Preferences prefs;
        prefs.begin("wifi", false);
        prefs.remove("ssid");
        prefs.remove("password");
        prefs.end();
        
        // Start configuration portal immediately
        startConfigPortal();
      }
    }
  }
  
  // Initialize monitoring system
  if (!initMonitoring()) {
    Serial.println("❌ Failed to initialize monitoring system");
  }
  
  // Initialize security system
  if (!initSecurity()) {
    Serial.println("❌ Failed to initialize security system");
  }
  
  // Initialize WiFi manager
  if (!initWiFiManager()) {
    Serial.println("❌ Failed to initialize WiFi manager");
  }
  
  // Initialize device management early so getCurrentDeviceId() is available for auth
  if (!initDeviceManagement()) {
    Serial.println("❌ Failed to initialize device management");
  }
  
  // Connect to WiFi (through WiFi manager) BEFORE OTA/Audio
  if (!isPortalActive()) {
    if (!connectToWiFi()) {
      // On cold boot, allow up to 20s to find/connect to a known network.
      // If still not connected after 20s, start the setup AP (portal).
      Preferences prefs;
      prefs.begin("wifi", true);
      String storedSsid = prefs.getString("ssid", "");
      prefs.end();

      if (storedSsid.length() > 0) {
        Serial.println("⏳ Searching for known WiFi for up to 20s...");
        unsigned long startWait = millis();
        // Kick off non-blocking reconnect attempts
        reconnectWiFi();
        while ((millis() - startWait) < 20000 && WiFi.status() != WL_CONNECTED) {
          handleWiFiManager();
          esp_task_wdt_reset();
          delay(50);
        }
      }

      if (WiFi.status() != WL_CONNECTED) {
        Serial.println("⚠️ No WiFi after 20s (or no saved creds). Starting config portal (AP)...");
        startConfigPortal();
      }
    }
  }
  
  // Wait indefinitely until Internet connectivity is verified
  Serial.println("⏳ Waiting for Internet connectivity (indefinite)...");
  waitForInternet(0);
  
  // Stop portal if still active once connected
  if (isPortalActive()) {
    stopWiFiPortal();
  }
  
  // If setup portal is active, defer heavy subsystems to keep AP stable
  if (WiFi.isConnected()) {
    authenticateDevice();
    
  // Initialize WebSocket connection
#ifdef PRODUCTION_BUILD
  // Production: require successful authentication and secure WS setup
  if (isAuthenticated()) {
    secureWebSocketConnect();
    connectWebSocket();
  }
#else
  // Development/local: skip JWT pairing; connect WS directly (server enforces HMAC)
  connectWebSocket();
#endif
  }
  
  // Initialize remaining systems only when portal is not active
  // Initialize OTA manager AFTER Internet connectivity
  if (!initOTA()) {
    Serial.println("❌ Failed to initialize OTA manager");
  }
  
  // Defer audio initialization until WebSocket is connected to avoid TLS memory pressure
  
  // Set runtime production mode based on build flag
  productionMode = PRODUCTION_MODE;
  
  Serial.println("✅ All production systems initialized");
}

void handleProductionLoop() {
  // Handle all production systems
  handleWiFiManager();
  handleOTA();
  handleMonitoring();
  checkSecurityHealth();
  handleDeviceManagement();
  
  // Handle WebSocket (loop + reconnection policy)
  handleWebSocketLoop();
}

void performStartupChecks() {
  if (!productionMode) return;
  
  // Perform health check
  bool allOk = performHealthCheck();
  
  // Check WiFi
  if (WiFi.status() != WL_CONNECTED) {
    logError(ERROR_WIFI_DISCONNECTED, "WiFi connection lost", "", 3);
    if (!reconnectWiFi()) {
      Serial.println("❌ WiFi reconnection failed");
    }
  }
  
  // Check authentication
  if (!isAuthenticated()) {
    logError(ERROR_AUTH_FAILED, "Device authentication lost", "", 2);
    authenticateDevice();
  }
}

// Indefinite wait for verified Internet connectivity while servicing portal and WiFi manager
bool waitForInternet(unsigned long timeoutMs) {
  unsigned long start = millis();
  unsigned long lastCheck = 0;
  while (true) {
    // Feed watchdog
    esp_task_wdt_reset();

    // Service systems needed during waiting
    handleWiFiManager();
    handleSetupMode();
    delay(10);

    // If WiFi connected, verify Internet every 3s
    if (WiFi.status() == WL_CONNECTED) {
      if (millis() - lastCheck > 3000) {
        Serial.println("🌐 Verifying Internet connectivity...");
        if (testInternetConnection()) {
          Serial.println("✅ Internet connectivity verified");
          return true;
        }
        lastCheck = millis();
      }
    }

    // Optional timeout handling
    if (timeoutMs > 0 && (millis() - start) > timeoutMs) {
      return false;
    }
  }
}

void handleButton() {
  // ✅ الحل المطلوب: Push-to-talk
  if (digitalRead(BUTTON_PIN) == LOW) {
    // عند الضغط على الزر
    if (getAudioState() == AUDIO_IDLE && isConnected) {
      logButtonInteraction("PRESSED", "WebSocket connected", "Starting audio recording");
      logAudioFlowState(AUDIO_FLOW_RECORDING, "Button pressed - Starting real-time streaming");
      startRealTimeStreaming(); // يبدأ streaming فوري
    }
  } else {
    // عند رفع الزر
    if (getAudioState() == AUDIO_STREAMING && isConnected) {
      logButtonInteraction("RELEASED", "Audio recording active", "Stopping audio recording");
      logAudioFlowState(AUDIO_FLOW_SENDING, "Button released - Stopping real-time streaming");
      stopRealTimeStreaming(); // يتوقف فوري
    }
  }
  
  // Debouncing for other button actions
  static unsigned long lastButtonAction = 0;
  if ((millis() - lastButtonAction) > DEBOUNCE_DELAY) {
    if (digitalRead(BUTTON_PIN) == LOW) {
      if (!isConnected) {
        // If not connected, show status
        printSystemStatus();
        playHappyAnimation();
        playTone(FREQ_HAPPY, 300);
      }
      lastButtonAction = millis();
    }
  }
}

void printSystemInfo() {
  logSystemEvent("System Information", "=== Production System Information ===");
  
  // Log system details using comprehensive logging
  logSystemStats((millis() - systemStartTime) / 1000, ESP.getFreeHeap(), 0.0);
  
  logSystemEvent("Device ID", getCurrentDeviceId());
  logSystemEvent("Firmware Version", FIRMWARE_VERSION);
  logSystemEvent("Production Mode", productionMode ? "Enabled" : "Disabled");
  logSystemEvent("Chip Model", ESP.getChipModel());
  logSystemEvent("MAC Address", WiFi.macAddress());
  logSystemEvent("WiFi Status", WiFi.isConnected() ? "Connected" : "Disconnected");
  logSystemEvent("Authentication", isAuthenticated() ? "Valid" : "Invalid");
  logSystemEvent("WebSocket", isConnected ? "Connected" : "Disconnected");
  
  // Log current flow states
  logCurrentFlowStates();
}
