/*
🧸 AI Teddy Bear ESP32 Client - Production Ready
===============================================
Connects ESP32 to AI Teddy Bear server for child-safe conversations

Server: ai-tiddy-bear-v-xuqy.onrender.com
WebSocket: /api/v1/esp32/chat
*/

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>

// 📡 WiFi Configuration - REPLACE WITH YOUR CREDENTIALS
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// 🎯 Server Configuration - UPDATED FOR NEW API STRUCTURE
const char* server_host = "ai-tiddy-bear-v-xuqy.onrender.com";
const int server_port = 443;
const char* ws_path = "/api/v1/esp32/chat";  // Updated path for new server structure

// 🔧 Hardware Configuration
const int LED_PIN = 2;        // Built-in LED
const int BUTTON_PIN = 0;     // Built-in button (BOOT button)
const int MICROPHONE_PIN = 34; // Analog pin for microphone
const int SPEAKER_PIN = 25;   // PWM pin for speaker

// 📱 Global Objects
WebSocketsClient webSocket;
bool isConnected = false;
bool wsConnecting = false; // Prevent parallel connection attempts
bool buttonPressed = false;
unsigned long lastHeartbeat = 0;

// Reconnection backoff management
struct ConnectionHealth {
  unsigned long reconnectDelay;     // current backoff delay (ms)
  unsigned long nextReconnectAt;    // millis() timestamp when a reconnect may be attempted
};

static const unsigned long RECONNECT_BASE_MS = 2000;   // 2s baseline
static const unsigned long RECONNECT_MAX_MS  = 60000;  // 60s cap
ConnectionHealth connectionHealth = { RECONNECT_BASE_MS, 0 };

void scheduleReconnection(unsigned long delayMs) {
  // Schedule next reconnect attempt after delayMs
  connectionHealth.nextReconnectAt = millis() + delayMs;
}

bool initWebSocket() {
  // Guard: require WiFi before attempting websocket
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi not connected, cannot init WebSocket");
    return false;
  }

  // Configure WebSocket connection
  webSocket.beginSSL(server_host, server_port, ws_path);
  webSocket.onEvent(webSocketEvent);
  // Disable library auto-reconnect; we manage scheduling explicitly
  webSocket.setReconnectInterval(0);
  // Keep heartbeat enabled
  webSocket.enableHeartbeat(15000, 3000, 2);

  return true; // Actual connection progresses asynchronously via webSocket.loop()
}

void setup() {
  Serial.begin(115200);
  Serial.println("🧸 AI Teddy Bear ESP32 Client Starting...");
  
  // Initialize pins
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(SPEAKER_PIN, OUTPUT);
  
  // Initial LED blink
  blinkLED(3);
  
  // Connect to WiFi
  connectToWiFi();
  
  // First connection attempt is scheduled immediately; init performed on demand
  scheduleReconnection(0);
  
  Serial.println("✅ Setup complete! Ready to connect to Teddy Bear server...");
}

void connectToWiFi() {
  Serial.print("📡 Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Blink while connecting
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("✅ WiFi Connected!");
    Serial.print("📍 IP Address: ");
    Serial.println(WiFi.localIP());
    digitalWrite(LED_PIN, HIGH); // Solid LED when connected
  } else {
    Serial.println();
    Serial.println("❌ WiFi Connection Failed!");
    // Continue anyway, will retry
  }
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("❌ WebSocket Disconnected from Teddy Bear Server");
      isConnected = false;
      wsConnecting = false; // Ensure we don't remain in connecting state
      digitalWrite(LED_PIN, LOW);
      // Schedule reconnection using current backoff, then increase backoff (capped)
      scheduleReconnection(connectionHealth.reconnectDelay);
      connectionHealth.reconnectDelay = min(connectionHealth.reconnectDelay * 2, RECONNECT_MAX_MS);
      break;
      
    case WStype_CONNECTED:
      Serial.printf("✅ WebSocket Connected to Teddy Bear Server!\n");
      Serial.printf("🔗 URL: %s\n", payload);
      isConnected = true;
      wsConnecting = false;
      // Reset backoff on successful connection
      connectionHealth.reconnectDelay = RECONNECT_BASE_MS;
      digitalWrite(LED_PIN, HIGH);
      
      // Send initial connection message
      sendConnectionMessage();
      break;
      
    case WStype_TEXT:
      Serial.printf("📥 Received from server: %s\n", payload);
      handleServerMessage((char*)payload);
      break;
      
    case WStype_BIN:
      Serial.printf("📦 Received binary data: %u bytes\n", length);
      break;
      
    case WStype_ERROR:
      Serial.printf("❌ WebSocket Error: %s\n", payload);
      isConnected = false;
      wsConnecting = false;
      // Unified reconnection scheduling on errors
      scheduleReconnection(connectionHealth.reconnectDelay);
      connectionHealth.reconnectDelay = min(connectionHealth.reconnectDelay * 2, RECONNECT_MAX_MS);
      break;
      
    case WStype_PING:
      Serial.println("💓 Ping from server");
      break;
      
    case WStype_PONG:
      Serial.println("💗 Pong from server");
      break;
  }
}

void sendConnectionMessage() {
  DynamicJsonDocument doc(1024);
  doc["type"] = "esp32_connect";
  doc["device_id"] = "teddy_bear_001";
  doc["firmware_version"] = "1.2.1";
  doc["features"] = "audio,button,led";
  doc["timestamp"] = millis();
  
  String message;
  serializeJson(doc, message);
  webSocket.sendTXT(message);
  
  Serial.println("📤 Sent connection message to server");
}

void handleServerMessage(String message) {
  DynamicJsonDocument doc(1024);
  deserializeJson(doc, message);
  
  String type = doc["type"];
  
  if (type == "audio_response") {
    String text = doc["text"];
    Serial.println("🔊 Playing audio response: " + text);
    playTone(1000, 500); // Simple beep for now
    
  } else if (type == "config_update") {
    Serial.println("⚙️ Received config update");
    
  } else if (type == "heartbeat") {
    Serial.println("💓 Heartbeat from server");
    lastHeartbeat = millis();
    
  } else {
    Serial.println("❓ Unknown message type: " + type);
  }
}

void sendChatMessage(String message) {
  if (!isConnected) {
    Serial.println("❌ Not connected to server");
    return;
  }
  
  DynamicJsonDocument doc(1024);
  doc["type"] = "chat_message";
  doc["device_id"] = "teddy_bear_001";
  doc["message"] = message;
  doc["timestamp"] = millis();
  
  String jsonString;
  serializeJson(doc, jsonString);
  webSocket.sendTXT(jsonString);
  
  Serial.println("📤 Sent: " + message);
}

void checkButton() {
  bool currentState = digitalRead(BUTTON_PIN) == LOW;
  
  if (currentState && !buttonPressed) {
    buttonPressed = true;
    Serial.println("🔵 Button pressed - sending test message");
    sendChatMessage("Hello, I'm your teddy bear! Tell me a story!");
    blinkLED(2);
    
  } else if (!currentState && buttonPressed) {
    buttonPressed = false;
    Serial.println("🔵 Button released");
  }
}

void blinkLED(int times) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(200);
    digitalWrite(LED_PIN, LOW);
    delay(200);
  }
}

void playTone(int frequency, int duration) {
  // Simple tone generation for speaker feedback
  tone(SPEAKER_PIN, frequency, duration);
  delay(duration);
  noTone(SPEAKER_PIN);
}

void loop() {
  // Handle WebSocket communication
  webSocket.loop();
  
  // Check WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("📡 WiFi disconnected, reconnecting...");
    connectToWiFi();
  }

  // Drive connection attempts with explicit scheduling and guard against parallel connects
  if (!isConnected && !wsConnecting) {
    unsigned long now = millis();
    if (now >= connectionHealth.nextReconnectAt) {
      wsConnecting = true;
      bool ok = initWebSocket();
      // Do not leave wsConnecting stuck true if init fails internally
      if (!ok) {
        wsConnecting = false;
        scheduleReconnection(connectionHealth.reconnectDelay);
        connectionHealth.reconnectDelay = min(connectionHealth.reconnectDelay * 2, RECONNECT_MAX_MS);
      }
    }
  }
  
  // Check button press
  checkButton();
  
  // Send periodic heartbeat
  if (isConnected && millis() - lastHeartbeat > 30000) {
    DynamicJsonDocument doc(256);
    doc["type"] = "heartbeat";
    doc["device_id"] = "teddy_bear_001";
    doc["timestamp"] = millis();
    
    String heartbeat;
    serializeJson(doc, heartbeat);
    webSocket.sendTXT(heartbeat);
    
    lastHeartbeat = millis();
    Serial.println("💓 Sent heartbeat to server");
  }
  
  // Small delay to prevent overwhelming the CPU
  delay(100);
}
