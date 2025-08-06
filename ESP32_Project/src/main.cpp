/*
🧸 AI TEDDY BEAR ESP32 - PRODUCTION CONTROLLER
============================================
Production-ready ESP32 with full management features
*/
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <FastLED.h>
#include <ESP32Servo.h>
#include <SPIFFS.h>
#include "config.h"
#include "hardware.h"
#include "websocket_handler.h"
#include "sensors.h"
#include "audio_handler.h"
#include "wifi_manager.h"
#include "ota_manager.h"
#include "monitoring.h"
#include "security.h"
#include "device_management.h"

// Production configuration
String deviceId = DEVICE_ID;

// Production system state
bool productionMode = false;
unsigned long systemStartTime = 0;

// Forward declarations
void initProductionSystems();
void handleProductionLoop();
void handleButton();
void printSystemInfo();
void performStartupChecks();

// Timing variables
unsigned long lastHeartbeat = 0;
unsigned long lastButtonPress = 0;
unsigned long lastSystemCheck = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("🧸 AI Teddy Bear ESP32 - Production Starting...");
  Serial.printf("Firmware Version: %s\n", FIRMWARE_VERSION);
  
  systemStartTime = millis();
  
  // Initialize all production systems
  initProductionSystems();
  
  Serial.println("✅ ESP32 AI Teddy Bear Production Ready!");
  printSystemInfo();
}

void loop() {
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
  }
  
  // Send heartbeat
  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
    sendHeartbeat();
    lastHeartbeat = millis();
  }
  
  // Update LEDs
  FastLED.show();
  
  delay(10);
}

void initProductionSystems() {
  Serial.println("🔧 Initializing production systems...");
  
  // Initialize SPIFFS for secure token storage
  if (!SPIFFS.begin(true)) {
    Serial.println("❌ Failed to initialize SPIFFS");
  } else {
    Serial.println("✅ SPIFFS initialized successfully");
  }
  
  // Initialize hardware first
  initHardware();
  
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
  
  // Initialize OTA manager
  if (!initOTA()) {
    Serial.println("❌ Failed to initialize OTA manager");
  }
  
  // Initialize device management
  if (!initDeviceManagement()) {
    Serial.println("❌ Failed to initialize device management");
  }
  
  // Initialize audio
  initAudio();
  
  // Connect to WiFi (through WiFi manager)
  if (!connectToWiFi()) {
    Serial.println("⚠️ WiFi connection failed, starting config portal");
    startConfigPortal();
  }
  
  // Authenticate device
  if (WiFi.isConnected()) {
    authenticateDevice();
    
    // Initialize WebSocket with security
    if (isAuthenticated()) {
      secureWebSocketConnect();
      initWebSocket();
    }
  }
  
  // Set production mode
  productionMode = true;
  
  Serial.println("✅ All production systems initialized");
}

void handleProductionLoop() {
  // Handle all production systems
  handleWiFiManager();
  handleOTA();
  handleMonitoring();
  checkSecurityHealth();
  handleDeviceManagement();
  
  // Handle WebSocket
  webSocket.loop();
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

void handleButton() {
  if (digitalRead(BUTTON_PIN) == LOW && 
      (millis() - lastButtonPress) > DEBOUNCE_DELAY) {
    
    Serial.println("🔘 Button pressed!");
    
    // Start audio recording if not busy
    if (getAudioState() == AUDIO_IDLE && isConnected) {
      startRecording();
    } else {
      // Fallback: send button event
      if (isConnected) {
        sendButtonEvent();
      } else {
        // If not connected, show status
        printSystemStatus();
      }
      playHappyAnimation();
      playTone(FREQ_HAPPY, 300);
    }
    
    lastButtonPress = millis();
  }
}

void printSystemInfo() {
  Serial.println("=== 🧸 Production System Information ===");
  Serial.printf("Device ID: %s\n", deviceId.c_str());
  Serial.printf("Firmware Version: %s\n", FIRMWARE_VERSION);
  Serial.printf("Production Mode: %s\n", productionMode ? "Enabled" : "Disabled");
  Serial.printf("Chip Model: %s\n", ESP.getChipModel());
  Serial.printf("Free Heap: %d bytes\n", ESP.getFreeHeap());
  Serial.printf("MAC Address: %s\n", WiFi.macAddress().c_str());
  Serial.printf("Uptime: %lu seconds\n", (millis() - systemStartTime) / 1000);
  Serial.printf("WiFi Status: %s\n", WiFi.isConnected() ? "Connected" : "Disconnected");
  Serial.printf("Authentication: %s\n", isAuthenticated() ? "Valid" : "Invalid");
  Serial.printf("WebSocket: %s\n", isConnected ? "Connected" : "Disconnected");
  Serial.println("========================================");
}