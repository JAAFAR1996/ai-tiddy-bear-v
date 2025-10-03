#include "websocket_handler.h"
#include "hardware.h"
#include "sensors.h"
#include "audio_handler.h"
#include "encoding_service.h"  // Professional encoding service
#include "security.h"  // Security and JWT integration
#include "jwt_manager.h"  // JWT Manager integration
#include "time_sync.h"  // Time validation for TLS
#include "device_id_manager.h"  // Dynamic device ID
#include "comprehensive_logging.h"  // Comprehensive logging system
#include <WiFi.h>
#include <vector>
#include <base64.h>  // Base64 encoding library
#include <mbedtls/md.h>  // For HMAC-SHA256
#include <mbedtls/sha256.h>
#include <esp_task_wdt.h>  // For watchdog reset
#include "config.h"  // For ESP32_SHARED_SECRET
#include "config_manager.h"  // For ConfigManager/TeddyConfig
#include "security/tls_roots.h"  // Root CAs for TLS validation

WebSocketsClient webSocket;
bool isConnected = false;
static volatile bool wsConnecting = false;
static String g_audio_session_id;
static volatile bool g_mark_final_next = false;

// Telemetry counters for audio TX
static unsigned long txStartMs = 0;
static unsigned long txLastReportMs = 0;
static uint32_t txChunks = 0;
static uint32_t txBytes = 0;
// Production connection resilience and health monitoring
struct ConnectionHealth {
  unsigned long lastPingTime = 0;
  unsigned long lastPongTime = 0;
  unsigned long rtt = 0; // Round trip time in ms
  unsigned long reconnectAttempts = 0;
  unsigned long reconnectDelay = 2000; // Start with 2 seconds
  unsigned long maxReconnectDelay = 60000; // Max 60 seconds
  unsigned long lastReconnectAttempt = 0;
  unsigned long connectionStartTime = 0;
  unsigned long totalDisconnections = 0;
  unsigned long packetsSent = 0;
  unsigned long packetsLost = 0;
  unsigned long lastHealthCheck = 0;
  bool connectionStable = true;
  float connectionScore = 100.0; // 0-100 connection quality score
  
  // Production ping/keepalive settings
  unsigned long lastKeepaliveTime = 0;
  unsigned long keepaliveInterval = 20000;   // 20 seconds as specified
  unsigned long pongTimeout = 10000;         // 10 second timeout as specified
  unsigned int missedPongs = 0;
  unsigned int maxMissedPongs = 5;           // Disconnect after 5 missed pongs
  bool awaitingPong = false;
};

static ConnectionHealth connectionHealth;

// Lightweight audio statistics for logging (PCM s16le)
inline void computeAudioStats(const uint8_t* pcm, size_t bytes, float& rms_dbfs, int16_t& peak_abs) {
  peak_abs = 0;
  if (!pcm || bytes < 2) { rms_dbfs = -120.0f; return; }
  const size_t samples = bytes / 2;
  double sum_sq = 0.0;
  for (size_t i = 0; i < samples; ++i) {
    int16_t s = (int16_t)((uint16_t)pcm[2*i] | ((uint16_t)pcm[2*i + 1] << 8));
    int16_t a = (s < 0) ? (int16_t)(-s) : s;
    if (a > peak_abs) peak_abs = a;
    sum_sq += (double)s * (double)s;
  }
  if (samples == 0) { rms_dbfs = -120.0f; return; }
  double rms = sqrt(sum_sq / (double)samples);
  if (rms <= 0.0001) { rms_dbfs = -120.0f; return; }
  rms_dbfs = (float)(20.0 * log10(rms / 32768.0));
}

void initWebSocket() {
  Serial.println("[WS] Initializing WebSocket with JWT authentication...");
  
  // Ensure device is authenticated first (production only)
#ifdef PRODUCTION_BUILD
  if (!isAuthenticated()) {
    Serial.println("[!] Device not authenticated, attempting authentication (production)...");
    if (!authenticateDevice()) {
      Serial.println("[ERROR] Failed to authenticate device for WebSocket connection (production)");
      return;
    }
  }
#else
  // Development/local: allow WS connect with HMAC-only (server enforces HMAC)
  if (!isAuthenticated()) {
    Serial.println("ℹ️ Proceeding without JWT (development) — server will verify HMAC token");
  }
#endif
  
  // Get JWT token and device information
  JWTManager* jwtManager = JWTManager::getInstance();
  String jwtToken = "";
  String deviceId = getCurrentDeviceId();
  String childId = "default";
  
  if (jwtManager && jwtManager->isTokenValid()) {
    jwtToken = jwtManager->getCurrentToken();
    deviceId = jwtManager->getDeviceId();
    childId = jwtManager->getChildId();
    Serial.println("✅ Using JWT Manager tokens for WebSocket connection");
  } else {
    Serial.println("⚠️ JWT Manager not available, using basic authentication");
    // Fallback to basic auth if needed
  }
  
  // Create WebSocket URL with query parameters and HMAC token (server-required)
  // Use the correct WebSocket path that matches the server
  String wsPath = "/api/v1/esp32/chat";
  wsPath += "?device_id=" + deviceId;
  wsPath += "&child_id=" + childId;

  // Pull child/server info from config if available
  String effectiveHost = String(SERVER_HOST);
  int effectivePort = SERVER_PORT;
  {
    extern ConfigManager configManager;
    TeddyConfig &cfg = configManager.getConfig();
    String childName = cfg.child_name.length() > 0 ? cfg.child_name : String("Friend");
    int childAge = (cfg.child_age >= 3 && cfg.child_age <= 13) ? cfg.child_age : 7;
    wsPath += "&child_name=" + childName;
    wsPath += "&child_age=" + String(childAge);
    if (cfg.server_host.length() > 0) effectiveHost = cfg.server_host;
    if (cfg.server_port > 0) effectivePort = cfg.server_port;
  }
  // Note: Do not append JWT here; server verifies HMAC token only

  // No token needed - simplified authentication with device_id only
  Serial.println("🔗 Using simplified authentication (device_id only)");
  
  // Decide scheme at runtime
  bool runtime_use_ssl = DEFAULT_SSL_ENABLED; // start from compile-time default
#ifdef PRODUCTION_BUILD
  // Production: honor compile-time default; do not auto-switch to TLS for local server
  (void)0;
#else
  // Development/staging: allow runtime override and local fallbacks
  {
    extern ConfigManager configManager;
    TeddyConfig &cfg = configManager.getConfig();
    runtime_use_ssl = cfg.ssl_enabled;
  }
  // For obvious local hosts/ports, force ws in non-production only
  if (effectivePort != 443 || effectiveHost == "127.0.0.1" || effectiveHost == "localhost" ||
      effectiveHost.startsWith("192.168." ) || effectiveHost.startsWith("10.") || effectiveHost.startsWith("172.")) {
    runtime_use_ssl = false;
  }
#endif

  String wsUrl = String(runtime_use_ssl ? "wss" : "ws") + "://" + effectiveHost + ":" + effectivePort + wsPath;
  Serial.printf("🔒 WebSocket URL: %s\n", wsUrl.c_str());
  
  // Connect with SSL/TLS if enabled
#if 1
  // Require valid time, but do it non-blocking: request SNTP and schedule retry
  if (runtime_use_ssl && !isTimeSynced()) {
    Serial.println("Defer WS until SNTP completes");
    requestSntpSync();
    scheduleReconnection(3000);
    return;
  }
#endif
  #if 1
    // STRICT TIME GATE: Validate time before any TLS connection
    if (runtime_use_ssl && !isTimeSynced()) {
      Serial.println("⏰ Time not synced, attempting NTP sync before SSL connection...");
      syncTimeWithNTP();
      delay(2000); // Additional wait for sync completion

      // Allow proceeding if system time looks sane (>= 2020-01-01), even if SNTP status not completed yet
      const unsigned long MIN_VALID_EPOCH = 1577836800UL; // 2020-01-01
      if (!isTimeSynced() && getCurrentTimestamp() < MIN_VALID_EPOCH) {
        Serial.println("❌ Time validation failed after NTP sync - blocking WebSocket TLS connection");
        return;
      } else if (!isTimeSynced()) {
        Serial.println("✅ Using estimated/system time for TLS (SNTP pending)");
      } else {
        Serial.println("✅ Time synchronized successfully for SSL connection");
      }
    }
    
    // Ensure CA store is available before TLS connect
    if (runtime_use_ssl && !ca_store_ready()) {
      Serial.println("CA store missing → abort connect");
      return;
    }
    // Provide explicit root CA to ensure CA validation works on Let's Encrypt chains
    if (runtime_use_ssl) {
      webSocket.beginSslWithCA(effectiveHost.c_str(), effectivePort, wsPath.c_str(), ISRG_ROOT_X1);
      Serial.printf("🔒 Secure WebSocket with CA verification: wss://%s:%d%s\n", 
                    effectiveHost.c_str(), effectivePort, wsPath.c_str());
    } else {
      // Skip TCP test and connect directly to avoid watchdog timeout
      Serial.println("🔗 Connecting WebSocket directly...");
      Serial.printf("Debug: Host='%s', Port=%d, Path='%s'\n", effectiveHost.c_str(), effectivePort, wsPath.c_str());
      
      // Add debugging headers
      webSocket.setExtraHeaders("Origin: http://192.168.0.139");
      
      webSocket.begin(effectiveHost.c_str(), effectivePort, wsPath);
      Serial.printf("🔗 WebSocket connecting to: ws://%s:%d%s\n", 
                    effectiveHost.c_str(), effectivePort, wsPath.c_str());
      
      // Force immediate connection attempt
      Serial.println("🚀 Forcing immediate WebSocket connection attempt...");
      webSocket.loop();
    }
  #endif
  
  // Configure WebSocket client; do NOT send Authorization header for device mode.
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(RECONNECT_INTERVAL);
  
  // Set longer connection timeout for WebSocket
  webSocket.enableHeartbeat(15000, 3000, 2);  // 15s ping interval, 3s pong timeout, 2 retries
  
  // Note: Server validates 'token' HMAC from query when 'device_id' is present.
  // Avoid adding Authorization header that could be misinterpreted as the token.
  
  // Set JWT refresh callback if JWT Manager is available
  if (jwtManager) {
    jwtManager->setRefreshCallback([](const String& refreshMessage) -> bool {
      return handleJWTRefreshMessage(refreshMessage);
    });
  }
}

static void attemptWebSocketConnect() {
  if (wsConnecting) return;
  wsConnecting = true;
#if USE_SSL
  if (!isTimeSynced()) {
    Serial.println("Defer WS until SNTP completes");
    requestSntpSync();
    scheduleReconnection(3000);
    wsConnecting = false;
    return;
  }
  if (!ca_store_ready()) {
    Serial.println("CA store missing → abort connect");
    scheduleReconnection(3000);
    wsConnecting = false;
    return;
  }
#endif
  initWebSocket();
  wsConnecting = false;
}

void connectWebSocket() {
  attemptWebSocketConnect();
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  Serial.printf("🔌 WebSocket Event: %d\n", type);
  
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("❌ WebSocket Disconnected");
      onWebSocketDisconnected();
      // Free audio resources on disconnect to relieve memory pressure
      cleanupAudio();
      break;
      
    case WStype_CONNECTED:
      Serial.printf("✅ WebSocket Connected to: %s\n", payload);
      onWebSocketConnected();
      // Initialize audio after network is up to avoid TLS memory pressure
      initAudio();
      break;
      
    case WStype_TEXT:
      Serial.printf("📨 Received JSON: %s\n", payload);
      onWebSocketMessageReceived();
      {
        String raw = String((char*)payload);
        String trimmed = raw; trimmed.trim();
        if (trimmed.equalsIgnoreCase("dev-ok") || trimmed.equalsIgnoreCase("ok")) {
          Serial.println("🔧 Non-JSON ack received; treating as auth/ok for dev mode");
          DynamicJsonDocument ack(64);
          ack["type"] = "auth/ok";
          handleAuthenticationResponse(ack, true);
          break;
        }
        handleIncomingMessage(raw);
      }
      break;
      
    case WStype_BIN:
      Serial.printf("🎵 Received binary audio frame: %d bytes\n", length);
      onWebSocketMessageReceived();
      handleIncomingAudioFrame(payload, length);
      break;
      
    case WStype_PONG:
      // Handle pong response for production keepalive
      connectionHealth.lastPongTime = millis();
      connectionHealth.rtt = connectionHealth.lastPongTime - connectionHealth.lastPingTime;
      connectionHealth.awaitingPong = false;
      connectionHealth.missedPongs = 0; // Reset missed pong counter
      
      Serial.printf("💗 Pong received - RTT: %lu ms\n", connectionHealth.rtt);
      
      // Update connection score based on RTT
      if (connectionHealth.rtt < 100) {
        connectionHealth.connectionScore = min(connectionHealth.connectionScore + 2.0f, 100.0f);
      } else if (connectionHealth.rtt > 500) {
        connectionHealth.connectionScore = max(connectionHealth.connectionScore - 5.0f, 0.0f);
      }
      break;
      
    case WStype_ERROR:
      Serial.printf("❌ WebSocket Error\n");
      onWebSocketError();
      break;
      
    default:
      break;
  }
}

void handleIncomingMessage(String message) {
  logWebSocketMessage("RECEIVE", "message", message.length());
  DynamicJsonDocument doc(2048);  // Increased size for new server protocol
  DeserializationError error = deserializeJson(doc, message);
  
  if (error) {
    Serial.printf("❌ JSON Parse Error: %s\n", error.c_str());
    return;
  }
  
  String type = doc["type"] | "";
  Serial.printf("🎯 Server Message Type: %s\n", type.c_str());
  
  // Handle NEW server protocol message types:
  if (type == "welcome") {
    handleWelcomeMessage(doc);
  }
  else if (type == "policy") {
    handlePolicyUpdate(doc);
  }
  else if (type == "alert") {
    handleSecurityAlert(doc);
  }
  else if (type == "auth/ok") {
    handleAuthenticationResponse(doc, true);
  }
  else if (type == "auth/error") {
    handleAuthenticationResponse(doc, false);
  }
  else if (type == "system") {
    // Handle system messages (e.g., audio ACKs from server)
    JsonVariant data = doc["data"];
    if (!data.isNull()) {
      String sysType = data["type"] | "";
      if (sysType == "audio_ack") {
        String chunkId = data["chunk_id"] | "";
        int bytes = data["bytes"] | 0;
        bool finalChunk = data["final"] | false;
        Serial.printf("[WS] Audio ACK: chunk=%s bytes=%d final=%s\n",
                      chunkId.c_str(), bytes, finalChunk ? "true" : "false");
      } else if (sysType == "audio_start_ack") {
        g_audio_session_id = (const char*)(data["audio_session_id"] | "");
        Serial.printf("[WS] Audio session started: %s\n", g_audio_session_id.c_str());
      }
    }
  }
  else if (type == "stream_start") {
    // Start real-time audio streaming without needing a hardware button
    if (getAudioState() != AUDIO_STREAMING && isConnected) {
      startRealTimeStreaming();
      DynamicJsonDocument ack(128);
      ack["type"] = "stream_ack";
      ack["status"] = "started";
      String msg; serializeJson(ack, msg);
      webSocket.sendTXT(msg);
    }
  }
  else if (type == "stream_stop") {
    if (getAudioState() == AUDIO_STREAMING) {
      stopRealTimeStreaming();
      DynamicJsonDocument ack(128);
      ack["type"] = "stream_ack";
      ack["status"] = "stopped";
      String msg; serializeJson(ack, msg);
      webSocket.sendTXT(msg);
    }
  }
  // Legacy message types for backward compatibility
  else if (type == "audio_response") {
    handleAudioResponse(doc["params"]);
  }
  else if (type == "led_control") {
    handleLEDCommand(doc["params"]);
  }
  else if (type == "animation") {
    handleAnimationCommand(doc["params"]);
  }
  else if (type == "status_check") {
    handleStatusRequest();
  }
  else if (type == "error") {
    String errorCode = doc["error_code"] | "";
    String errorMessage = doc["error_message"] | "";
    Serial.printf("❌ Server Error [%s]: %s\n", errorCode.c_str(), errorMessage.c_str());
    setLEDColor("red", 100);
    delay(1000);
    clearLEDs();
  }
  else if (type == "text_response") {
    String txt = doc["text"] | "";
    Serial.printf("[WS] Text response: %s\n", txt.c_str());
  }
  else {
    Serial.printf("⚠️ Unknown message type: %s\n", type.c_str());
  }
}

void sendHandshake() {
  DynamicJsonDocument doc(512);
  doc["type"] = "handshake";
  doc["device_id"] = getCurrentDeviceId();
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["timestamp"] = millis();
  doc["protocol_version"] = "1.0";
  
  // إضافة معلومات الطفل (يمكن جعلها configurable)
  doc["child_id"] = "child-001";
  doc["child_name"] = "TestChild";
  doc["child_age"] = 7;
  
  JsonArray capabilities = doc.createNestedArray("capabilities");
  capabilities.add("led_control");
  capabilities.add("audio_play");
  capabilities.add("animation");
  capabilities.add("sensor_read");
  capabilities.add("audio_recording");
  capabilities.add("audio_playback");
  
  JsonObject hardware = doc.createNestedObject("hardware");
  hardware["leds"] = NUM_LEDS;
  hardware["speaker"] = true;
  hardware["microphone"] = true;
  hardware["i2s_audio"] = true;
  
  String message;
  serializeJson(doc, message);
  webSocket.sendTXT(message);
  
  Serial.println("🤝 Handshake sent with child info");
}

void sendSensorData() {
  DynamicJsonDocument doc(512);
  doc["type"] = "sensor_data";
  doc["device_id"] = getCurrentDeviceId();
  doc["timestamp"] = millis();
  
  SensorData data = readAllSensors();
  JsonObject sensorData = doc.createNestedObject("data");
  sensorData["wifi_strength"] = data.wifiStrength;
  sensorData["uptime"] = data.uptime;
  sensorData["free_heap"] = data.freeHeap;
  
  String message;
  serializeJson(doc, message);
  webSocket.sendTXT(message);
  
  Serial.println("📊 Sensor data sent");
}

void sendHeartbeat() {
  if (!isConnected) return;
  
  DynamicJsonDocument doc(256);
  doc["type"] = "heartbeat";
  doc["device_id"] = getCurrentDeviceId();
  doc["timestamp"] = millis();
  doc["status"] = "alive";
  
  String message;
  serializeJson(doc, message);
  webSocket.sendTXT(message);
  
  Serial.println("💓 Heartbeat sent");
}

void sendResponse(String status, String message, String requestId) {
  DynamicJsonDocument doc(256);
  doc["type"] = "response";
  doc["status"] = status;
  doc["message"] = message;
  doc["device_id"] = getCurrentDeviceId();
  doc["timestamp"] = millis();
  
  if (requestId != "") {
    doc["request_id"] = requestId;
  }
  
  String response;
  serializeJson(doc, response);
  webSocket.sendTXT(response);
}

void sendDeviceStatus() {
  DynamicJsonDocument doc(512);
  doc["type"] = "device_status";
  doc["device_id"] = getCurrentDeviceId();
  doc["timestamp"] = millis();
  
  JsonObject status = doc.createNestedObject("status");
  status["connected"] = isConnected;
  status["wifi_connected"] = WiFi.status() == WL_CONNECTED;
  status["ip_address"] = WiFi.localIP().toString();
  status["mac_address"] = WiFi.macAddress();
  status["free_heap"] = ESP.getFreeHeap();
  status["uptime"] = millis();
  status["firmware_version"] = FIRMWARE_VERSION;
  
  String message;
  serializeJson(doc, message);
  webSocket.sendTXT(message);
  
  Serial.println("📋 Device status sent");
}

// Command Handlers
void handleLEDCommand(JsonObject params) {
  String color = params["color"] | "white";
  int brightness = params["brightness"] | LED_BRIGHTNESS;
  
  setLEDColor(color, brightness);
}


void handleAudioCommand(JsonObject params) {
  String audioType = params["file"] | "default";
  int volume = params["volume"] | 50;
  (void)volume; // Suppress unused variable warning
  
  int frequency = FREQ_DEFAULT;
  int duration = 500;
  
  if (audioType == "happy") {
    frequency = FREQ_HAPPY;
    duration = 300;
  } else if (audioType == "sad") {
    frequency = FREQ_SAD;
    duration = 800;
  } else if (audioType == "excited") {
    frequency = FREQ_EXCITED;
    duration = 200;
  }
  
  playTone(frequency, duration);
}

void handleAnimationCommand(JsonObject params) {
  String animType = params["type"] | "happy";
  
  if (animType == "happy") {
    playHappyAnimation();
  } else if (animType == "sad") {
    playSadAnimation();
  } else if (animType == "excited") {
    playExcitedAnimation();
  } else if (animType == "rainbow") {
    playRainbowAnimation();
  } else if (animType == "welcome") {
    playWelcomeAnimation();
  }
}

void handleStatusRequest() {
  sendDeviceStatus();
}

// Connection event handlers
void onWebSocketConnected() {
  isConnected = true;
  connectionHealth.connectionStartTime = millis();
  connectionHealth.reconnectAttempts = 0;
  connectionHealth.reconnectDelay = 1000; // Reset to initial delay
  connectionHealth.connectionStable = true;
  connectionHealth.connectionScore = 100.0;
  
  // Reset production keepalive state
  connectionHealth.lastKeepaliveTime = millis();
  connectionHealth.missedPongs = 0;
  connectionHealth.awaitingPong = false;
  
  sendHandshake();
  playWelcomeAnimation();
  
  Serial.printf("✅ Connection established - Score: %.1f%% (Keepalive: %lus)\n", 
                connectionHealth.connectionScore, connectionHealth.keepaliveInterval / 1000);
}

void onWebSocketDisconnected() {
  isConnected = false;
  connectionHealth.totalDisconnections++;
  connectionHealth.connectionStable = false;
  connectionHealth.connectionScore = max(connectionHealth.connectionScore - 10.0f, 0.0f);
  
  setLEDColor("red", 50);
  delay(500);
  clearLEDs();
  
  Serial.printf("❌ Connection lost (Total: %lu) - Score: %.1f%%\n", 
                connectionHealth.totalDisconnections, connectionHealth.connectionScore);
  
  // Start exponential backoff reconnection
  connectionHealth.reconnectDelay = min(connectionHealth.reconnectDelay * 2, connectionHealth.maxReconnectDelay);
  scheduleReconnection(connectionHealth.reconnectDelay);
}

void onWebSocketError() {
  connectionHealth.packetsLost++;
  connectionHealth.connectionScore = max(connectionHealth.connectionScore - 5.0f, 0.0f);
  Serial.printf("❌ WebSocket error - Packet loss: %lu, Score: %.1f%%\n", 
                connectionHealth.packetsLost, connectionHealth.connectionScore);
  
  // Trigger reconnection on persistent errors
  if (connectionHealth.packetsLost % 5 == 0) {
    scheduleReconnection(connectionHealth.reconnectDelay);
  }
}

void onWebSocketMessageReceived() {
  // Update connection health on successful message receipt
  connectionHealth.connectionScore = min(connectionHealth.connectionScore + 1.0f, 100.0f);
}

void scheduleReconnection() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ WiFi not connected, skipping WebSocket reconnection");
    return;
  }
  
  unsigned long now = millis();
  
  // Check if we should attempt reconnection (exponential backoff)
  if (now - connectionHealth.lastReconnectAttempt < connectionHealth.reconnectDelay) {
    return;
  }
  
  connectionHealth.lastReconnectAttempt = now;
  connectionHealth.reconnectAttempts++;
  
  Serial.printf("🔄 Reconnection attempt #%lu (delay: %lu ms)\n", 
                connectionHealth.reconnectAttempts, connectionHealth.reconnectDelay);
  
  webSocket.disconnect();
  delay(100);
  initWebSocket();
  
  // Exponential backoff with jitter
  connectionHealth.reconnectDelay = min(connectionHealth.reconnectDelay * 2, 
                                       connectionHealth.maxReconnectDelay);
  
  // Add jitter (±20%)
  long jitter = (connectionHealth.reconnectDelay * 20) / 100;
  connectionHealth.reconnectDelay += random(-jitter, jitter);
}

// Schedule reconnection after a specific delay without attempting immediately
void scheduleReconnection(unsigned long delayMs) {
  if (delayMs == 0) delayMs = 1000;
  connectionHealth.reconnectDelay = delayMs;
  connectionHealth.lastReconnectAttempt = millis();
  Serial.printf("Reconnection scheduled in %lu ms\n", delayMs);
}

void reconnectWebSocket() {
  if (connectionHealth.reconnectDelay == 0) {
    connectionHealth.reconnectDelay = 2000;
  }
  connectionHealth.lastReconnectAttempt = millis();
  connectWebSocket();
}

String createMessage(String type, JsonObject data) {
  DynamicJsonDocument doc(512);
  doc["type"] = type;
  doc["device_id"] = getCurrentDeviceId();
  doc["timestamp"] = millis();
  
  if (!data.isNull()) {
    doc["data"] = data;
  }
  
  String message;
  serializeJson(doc, message);
  return message;
}

void handleAudioResponseWebSocket(JsonObject params) {
  String audioDataB64 = params["audio_data"] | "";
  String text = params["text"] | "";
  String format = params["format"] | "pcm_s16le";
  int audioRate = params["audio_rate"] | 22050;
  
  logWebSocketMessage("RECEIVE", "audio_response", audioDataB64.length());
  updateAudioFlowState(AUDIO_FLOW_RECEIVING);
  logAudioEvent("Audio response received", "Text: " + text);
  
  if (audioDataB64.length() > 0) {
    // Only PCM s16le is supported on-device without heavy decoders
    String fmtLower = format; fmtLower.toLowerCase();
    bool pcmOk = (fmtLower.indexOf("pcm") != -1) || (fmtLower.indexOf("s16") != -1);
    if (!pcmOk) {
      Serial.printf("❌ Unsupported audio format from server: %s (expected pcm_s16le)\n", format.c_str());
      return;
    }
    Serial.printf("🔊 Received audio response: %s\n", text.c_str());
    Serial.printf("📊 Format: %s, Rate: %d Hz\n", format.c_str(), audioRate);
    
    // Decode base64 audio
    std::vector<uint8_t> audioData;
    if (audioDataB64.length() > 0) {
      // احسب حجم الـ buffer المطلوب أولاً
      unsigned int requiredSize = calculateBase64EncodedSize(audioDataB64.length());
      unsigned char* audioBuffer = new unsigned char[requiredSize];
      unsigned int audioLen = decodeBase64(audioDataB64.c_str(), audioBuffer, requiredSize);
      audioData.assign(audioBuffer, audioBuffer + audioLen);
      delete[] audioBuffer;
    }
    
    if (audioData.size() > 0) {
      logAudioData("Received", audioData.size(), format);
      updateAudioFlowState(AUDIO_FLOW_PLAYING);
      logAudioEvent("Starting audio playback", "Size: " + String(audioData.size()) + " bytes, Format: " + format);
      
      // Show speaking animation
      setLEDColor("green", 80);
      logLEDAnimation("speaking", "green", 2500);
      
      // Play the audio (implement actual audio playback here)
      playAudioResponse(audioData.data(), audioData.size());
      
      // Show completion
      playHappyAnimation();
      clearLEDs();
    } else {
      Serial.println("❌ Failed to decode audio data");
      setLEDColor("red", 50);
      delay(500);
      clearLEDs();
    }
  } else {
    Serial.println("❌ No audio data received");
  }
}

// Network performance monitoring
__attribute__((unused)) static unsigned long lastChunkTime = 0;
static size_t adaptiveChunkSize = 4096; // Start with 4KB chunks
static int consecutiveTimeouts = 0;

// Calculate HMAC-SHA256 for audio frame authentication
String calculateAudioHMACWebSocket(uint8_t* audioData, size_t length, const String& chunkId, const String& sessionId) {
  // Get device secret key for HMAC
  const char* deviceSecret = ESP32_SHARED_SECRET;
  if (!deviceSecret || strlen(deviceSecret) < 32) {
    Serial.println("❌ No device secret for audio HMAC");
    return "";
  }
  
  // Use secret as raw bytes (no HEX decoding)
  const uint8_t* keyBytes = (const uint8_t*)deviceSecret;
  size_t keyLen = strlen(deviceSecret);
  
  // Prepare HMAC context
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  
  const mbedtls_md_info_t* md_info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_setup(&ctx, md_info, 1); // 1 for HMAC
  
  // Start HMAC
  mbedtls_md_hmac_starts(&ctx, keyBytes, keyLen);
  
  // Update with audio data + metadata
  mbedtls_md_hmac_update(&ctx, audioData, length);
  mbedtls_md_hmac_update(&ctx, (const uint8_t*)chunkId.c_str(), chunkId.length());
  mbedtls_md_hmac_update(&ctx, (const uint8_t*)sessionId.c_str(), sessionId.length());
  
  // Finish HMAC
  uint8_t hmacResult[32];
  mbedtls_md_hmac_finish(&ctx, hmacResult);
  mbedtls_md_free(&ctx);
  
  // Convert to hex string
  char hexHmac[65];
  for (int i = 0; i < 32; i++) {
    sprintf(&hexHmac[i*2], "%02x", hmacResult[i]);
  }
  hexHmac[64] = '\0';
  
  return String(hexHmac);
}

void sendAudioDataWebSocket(uint8_t* audioData, size_t length) {
  if (!isConnected || audioData == nullptr || length == 0) {
    logError("Audio", "Cannot send audio", "not connected or invalid data");
    return;
  }
  
  logAudioData("Sending", length, "PCM 16kHz mono s16le");
  updateAudioFlowState(AUDIO_FLOW_SENDING);
  
  unsigned long transmissionStart = millis();
  
  // Validate audio format expectations
  if (length != 4096 && length % 2 != 0) {
    Serial.printf("⚠️ Audio chunk size %d is not optimal (expected 4096B PCM chunks)\n", length);
  }
  
  // Generate unique identifiers
  String chunkId = String(millis()) + "_" + String(random(1000, 9999));
  String sessionId = String(millis() / 1000);
  
  // Calculate HMAC for audio authentication
  String audioHmac = calculateAudioHMACWebSocket(audioData, length, chunkId, sessionId);
  
  // ✅ الحل: تطابق مع بروتوكول السيرفر - JSON بدلاً من binary
  String base64Audio = base64::encode(audioData, length);
  // Allocate JSON capacity based on Base64 size to avoid memory pressure
  // Base64 expands by ~4/3; add overhead for fields/HMAC
  DynamicJsonDocument doc(base64Audio.length() + 1024);
  doc["type"] = "audio_chunk";
  doc["audio_data"] = base64Audio;
  doc["chunk_id"] = chunkId;
  if (g_audio_session_id.length() > 0) {
    doc["audio_session_id"] = g_audio_session_id;
  }
  bool finalFlag = false;
  if (g_mark_final_next) { finalFlag = true; g_mark_final_next = false; }
  doc["is_final"] = finalFlag;
  // Log a short fingerprint and stats of the audio about to be sent
  {
    String b64prefix = base64Audio.substring(0, 16);
    float rms_db = 0.0f; int16_t peak = 0;
    computeAudioStats(audioData, length, rms_db, peak);
    Serial.printf("?? About to send audio: bytes=%d, samples=%d, peak=%d, rms=%.1f dBFS, b64=%.16s...\n",
                  (int)length, (int)(length/2), (int)peak, (double)rms_db, b64prefix.c_str());
  }
  
  // 🔒 Add HMAC for production security
  if (!audioHmac.isEmpty()) {
    doc["hmac"] = audioHmac;
#ifdef PRODUCTION_BUILD
    Serial.println("🔒 Audio HMAC added (production)");
#else
    Serial.printf("🔒 Audio HMAC: %s...\n", audioHmac.substring(0, 16).c_str());
#endif
  } else {
    Serial.println("⚠️ Audio sent without HMAC (security risk)");
  }
  
  String message;
  serializeJson(doc, message);
  bool success = webSocket.sendTXT(message);
  
  if (success) {
    connectionHealth.packetsSent++;
    consecutiveTimeouts = 0; // Reset timeout counter on success
    
    unsigned long transmissionTime = millis() - transmissionStart;
    Serial.printf("✅ Secure audio chunk sent: %d bytes in %lu ms\n", length, transmissionTime);
    Serial.printf("[AUDIO][TX] sent bytes=%d time_ms=%lu\\n", (int)length, transmissionTime);
    if (txChunks == 0) { txStartMs = millis(); txLastReportMs = txStartMs; }
    txChunks++; txBytes += (uint32_t)length;
    unsigned long now = millis();
    if (now - txLastReportMs >= 2000) {
      float sec = (now - txStartMs) / 1000.0f;
      float kbps = sec > 0 ? (txBytes * 8.0f) / 1000.0f / sec : 0.0f;
      Serial.printf("[TRACE][AUDIO] tx_chunks=%u tx_bytes=%u avg_kbps=%.1f uptime_s=%.1f\\n", txChunks, txBytes, kbps, sec);
      txLastReportMs = now;
    }
    
    // Update connection quality based on transmission speed
    if (transmissionTime > 100) {
      connectionHealth.connectionScore = max(connectionHealth.connectionScore - 1.0f, 0.0f);
    } else {
      connectionHealth.connectionScore = min(connectionHealth.connectionScore + 0.5f, 100.0f);
    }
  } else {
    connectionHealth.packetsLost++;
    consecutiveTimeouts++;
    
    Serial.printf("❌ Failed to send binary audio frame (%d bytes)\n", length);
    
    // Trigger reconnection after multiple consecutive failures
    if (consecutiveTimeouts >= 3) {
      Serial.println("🔄 Multiple audio transmission failures, triggering reconnection");
      scheduleReconnection(connectionHealth.reconnectDelay);
    }
  }
  
  // Real-time audio requires minimal delay
  yield();
}

// Public helpers to control audio sessions from other modules
void sendAudioStartSession() {
  if (!isConnected) return;
  DynamicJsonDocument doc(128);
  doc["type"] = "audio_start";
  String msg; serializeJson(doc, msg);
  webSocket.sendTXT(msg);
}

void sendAudioEndSession() {
  if (!isConnected) return;
  DynamicJsonDocument doc(192);
  doc["type"] = "audio_end";
  if (g_audio_session_id.length() > 0) doc["audio_session_id"] = g_audio_session_id;
  String msg; serializeJson(doc, msg);
  webSocket.sendTXT(msg);
}

void markNextChunkFinal() {
  g_mark_final_next = true;
}

// Adaptive chunk sizing functions
size_t getOptimalChunkSize() {
  // Adjust based on WiFi signal strength and recent performance
  int rssi = WiFi.RSSI();
  
  if (rssi > -50 && consecutiveTimeouts == 0) {
    // Excellent signal, use larger chunks
    return min(adaptiveChunkSize, (size_t)8192);
  } else if (rssi > -70 && consecutiveTimeouts < 2) {
    // Good signal, use medium chunks
    return min(adaptiveChunkSize, (size_t)4096);
  } else {
    // Poor signal or recent timeouts, use smaller chunks
    return min(adaptiveChunkSize, (size_t)1024);
  }
}

void adjustChunkSizeDown() {
  adaptiveChunkSize = max(adaptiveChunkSize / 2, (size_t)512);
  Serial.printf("🔽 Reduced chunk size to %d bytes\n", adaptiveChunkSize);
}

void adjustChunkSizeUp() {
  if (consecutiveTimeouts == 0) {
    adaptiveChunkSize = min((size_t)(adaptiveChunkSize * 1.5), (size_t)8192);
    Serial.printf("🔼 Increased chunk size to %d bytes\n", adaptiveChunkSize);
  }
}

void logMessage(String direction, String message) {
  Serial.printf("[%s] %s\n", direction.c_str(), message.c_str());
}

// Connection health monitoring functions
void updateConnectionQuality() {
  // Calculate packet loss rate
  float lossRate = 0.0;
  if (connectionHealth.packetsSent > 0) {
    lossRate = (float)connectionHealth.packetsLost / (float)connectionHealth.packetsSent * 100.0;
  }
  
  // Update connection score based on multiple factors
  float scoreAdjustment = 0;
  
  // WiFi signal strength factor
  int rssi = WiFi.RSSI();
  if (rssi > -50) scoreAdjustment += 10;        // Excellent
  else if (rssi > -60) scoreAdjustment += 5;    // Good
  else if (rssi > -70) scoreAdjustment += 0;    // Fair
  else scoreAdjustment -= 5;                    // Poor
  
  // RTT factor
  if (connectionHealth.rtt < 50) scoreAdjustment += 5;      // Excellent
  else if (connectionHealth.rtt < 100) scoreAdjustment += 2; // Good
  else if (connectionHealth.rtt > 500) scoreAdjustment -= 10; // Poor
  
  // Packet loss factor
  if (lossRate < 1.0) scoreAdjustment += 5;     // Excellent
  else if (lossRate < 5.0) scoreAdjustment += 0; // Acceptable
  else scoreAdjustment -= (lossRate * 2);       // Poor
  
  // Update connection score with bounds
  connectionHealth.connectionScore = constrain(
    connectionHealth.connectionScore + scoreAdjustment * 0.1, 0.0, 100.0
  );
  
  // Determine connection stability
  connectionHealth.connectionStable = (
    connectionHealth.connectionScore > 70.0 &&
    lossRate < 5.0 &&
    connectionHealth.rtt < 200 &&
    isConnected
  );
}

void sendPingFrame() {
  if (isConnected) {
    connectionHealth.lastPingTime = millis();
    webSocket.sendPing();
    Serial.println("📊 Ping sent for RTT measurement");
  }
}

// Production ping with keepalive tracking
void sendProductionPing() {
  if (!isConnected) return;
  
  connectionHealth.lastPingTime = millis();
  connectionHealth.awaitingPong = true;
  
  bool success = webSocket.sendPing();
  if (success) {
    Serial.printf("💓 Keepalive ping sent (interval: %lums)\n", connectionHealth.keepaliveInterval);
  } else {
    Serial.println("❌ Failed to send keepalive ping");
    connectionHealth.packetsLost++;
  }
}

void performConnectionHealthCheck() {
  unsigned long now = millis();
  
  // Production keepalive: send ping every 20 seconds
  if (isConnected && (now - connectionHealth.lastKeepaliveTime > connectionHealth.keepaliveInterval)) {
    sendProductionPing();
    connectionHealth.lastKeepaliveTime = now;
  }
  
  // Check for pong timeout (10 seconds)
  if (connectionHealth.awaitingPong && 
      (now - connectionHealth.lastPingTime > connectionHealth.pongTimeout)) {
    
    connectionHealth.missedPongs++;
    connectionHealth.awaitingPong = false;
    
    Serial.printf("⚠️ Pong timeout (missed: %u/%u)\n", 
                  connectionHealth.missedPongs, connectionHealth.maxMissedPongs);
    
    // Disconnect after too many missed pongs
    if (connectionHealth.missedPongs >= connectionHealth.maxMissedPongs) {
      Serial.println("💔 Too many missed pongs, triggering reconnection");
      connectionHealth.missedPongs = 0;
      scheduleReconnection(connectionHealth.reconnectDelay);
      return;
    }
  }
  
  // Perform detailed health check every 30 seconds
  if (now - connectionHealth.lastHealthCheck > 30000) {
    connectionHealth.lastHealthCheck = now;
    
    updateConnectionQuality();
    
    // Log health status
    Serial.printf("🏥 Connection Health - Score: %.1f%%, RTT: %lu ms, Pongs: %u/%u\n",
                  connectionHealth.connectionScore, connectionHealth.rtt,
                  connectionHealth.missedPongs, connectionHealth.maxMissedPongs);
    
    // Trigger reconnection if connection quality is very poor
    if (connectionHealth.connectionScore < 20.0 && isConnected) {
      Serial.println("⚠️ Connection quality critically low, triggering reconnection");
      scheduleReconnection(connectionHealth.reconnectDelay);
    }
  }
}

// Enhanced network performance monitoring
void printNetworkStats() {
  updateConnectionQuality();
  
  float lossRate = 0.0;
  if (connectionHealth.packetsSent > 0) {
    lossRate = (float)connectionHealth.packetsLost / (float)connectionHealth.packetsSent * 100.0;
  }
  
  unsigned long uptime = millis() - connectionHealth.connectionStartTime;
  
  Serial.println("=== [WS]� Network Performance & Connection Health ===");
  Serial.printf("WiFi RSSI: %d dBm\n", WiFi.RSSI());
  Serial.printf("WebSocket Connected: %s\n", isConnected ? "Yes" : "No");
  Serial.printf("Connection Score: %.1f%%\n", connectionHealth.connectionScore);
  Serial.printf("Connection Stable: %s\n", connectionHealth.connectionStable ? "Yes" : "No");
  Serial.printf("RTT: %lu ms\n", connectionHealth.rtt);
  Serial.printf("Uptime: %lu ms\n", uptime);
  Serial.printf("Total Disconnections: %lu\n", connectionHealth.totalDisconnections);
  Serial.printf("Reconnect Attempts: %lu\n", connectionHealth.reconnectAttempts);
  Serial.printf("Packets Sent: %lu\n", connectionHealth.packetsSent);
  Serial.printf("Packets Lost: %lu (%.2f%%)\n", connectionHealth.packetsLost, lossRate);
  Serial.printf("Adaptive Chunk Size: %d bytes\n", adaptiveChunkSize);
  Serial.printf("Consecutive Timeouts: %d\n", consecutiveTimeouts);
  Serial.printf("Next Reconnect Delay: %lu ms\n", connectionHealth.reconnectDelay);
  Serial.printf("Keepalive Interval: %lu s\n", connectionHealth.keepaliveInterval / 1000);
  Serial.printf("Missed Pongs: %u/%u\n", connectionHealth.missedPongs, connectionHealth.maxMissedPongs);
  Serial.printf("Awaiting Pong: %s\n", connectionHealth.awaitingPong ? "Yes" : "No");
  Serial.println("===============================================");
}

void getConnectionHealth(JsonObject& healthObj) {
  updateConnectionQuality();
  
  float lossRate = 0.0;
  if (connectionHealth.packetsSent > 0) {
    lossRate = (float)connectionHealth.packetsLost / (float)connectionHealth.packetsSent * 100.0;
  }
  
  healthObj["connected"] = isConnected;
  healthObj["score"] = connectionHealth.connectionScore;
  healthObj["stable"] = connectionHealth.connectionStable;
  healthObj["rtt"] = connectionHealth.rtt;
  healthObj["wifi_rssi"] = WiFi.RSSI();
  healthObj["uptime"] = millis() - connectionHealth.connectionStartTime;
  healthObj["disconnections"] = connectionHealth.totalDisconnections;
  healthObj["reconnect_attempts"] = connectionHealth.reconnectAttempts;
  healthObj["packets_sent"] = connectionHealth.packetsSent;
  healthObj["packets_lost"] = connectionHealth.packetsLost;
  healthObj["packet_loss_rate"] = lossRate;
  healthObj["chunk_size"] = adaptiveChunkSize;
  healthObj["keepalive_interval"] = connectionHealth.keepaliveInterval;
  healthObj["missed_pongs"] = connectionHealth.missedPongs;
  healthObj["awaiting_pong"] = connectionHealth.awaitingPong;
}

// Enhanced connection state management
void handleWebSocketLoop() {
  // Handle WebSocket loop
  webSocket.loop();
  
  // Perform periodic connection health checks
  performConnectionHealthCheck();
  
  // Handle automatic reconnection if needed
  if (!isConnected && WiFi.status() == WL_CONNECTED) {
    unsigned long now = millis();
    if (now - connectionHealth.lastReconnectAttempt >= connectionHealth.reconnectDelay) {
      reconnectWebSocket();
    }
  }
}

void sendConnectionHealthReport() {
  if (!isConnected) return;
  
  DynamicJsonDocument doc(1024);
  doc["type"] = "connection_health_report";
  doc["device_id"] = getCurrentDeviceId();
  doc["timestamp"] = millis();
  
  JsonObject health = doc.createNestedObject("health");
  getConnectionHealth(health);
  
  String message;
  serializeJson(doc, message);
  
  if (webSocket.sendTXT(message)) {
    Serial.println("📊 Connection health report sent");
  } else {
    Serial.println("❌ Failed to send connection health report");
  }
}

bool isConnectionHealthy() {
  updateConnectionQuality();
  return connectionHealth.connectionStable && 
         connectionHealth.connectionScore > 50.0 && 
         isConnected;
}

// Moved to connection_stats.cpp to avoid duplicate definition
extern void resetConnectionStats();

void resetLocalConnectionStats() {
  connectionHealth.packetsSent = 0;
  connectionHealth.packetsLost = 0;
  connectionHealth.totalDisconnections = 0;
  connectionHealth.reconnectAttempts = 0;
  connectionHealth.connectionScore = 100.0;
  connectionHealth.reconnectDelay = 1000;
  Serial.println("🔄 Local connection statistics reset");
}

// ===== NEW SERVER PROTOCOL HANDLERS =====

/**
 * Handle Welcome message from server
 * Format: {"type": "welcome", "audio": {"sample_rate": 16000, "channels": 1, "format": "pcm_s16le"}}
 */
void handleWelcomeMessage(DynamicJsonDocument& doc) {
  Serial.println("🎉 Received welcome message from server");
  
  // Extract audio configuration
  if (doc.containsKey("audio")) {
    JsonObject audio = doc["audio"];
    int sampleRate = audio["sample_rate"] | 16000;
    int channels = audio["channels"] | 1;
    String format = audio["format"] | "pcm_s16le";
    
    Serial.printf("🔊 Server audio config - Rate: %dHz, Channels: %d, Format: %s\n", 
                  sampleRate, channels, format.c_str());
    
    // Validate and configure audio settings
    if (sampleRate == 16000 && channels == 1 && format == "pcm_s16le") {
      Serial.println("✅ Audio configuration compatible");
      // Configure audio handler for 16kHz mono PCM
      // configureAudioHandler(sampleRate, channels, format); // Implement in audio_handler.cpp
    } else {
      Serial.printf("⚠️ Audio configuration mismatch - using defaults\n");
    }
  }
  
  // Show welcome animation
  playWelcomeAnimation();
  setLEDColor("green", 70);
  delay(1000);
  clearLEDs();
}

/**
 * Handle Policy Update message from server
 * Format: {"type": "policy", "child_id": "uuid", "age": 7, "filters": {"content": "strict", "blocked_topics": ["violence"]}}
 */
void handlePolicyUpdate(DynamicJsonDocument& doc) {
  Serial.println("📋 Received policy update from server");
  
  String childId = doc["child_id"] | "";
  int age = doc["age"] | 0;
  
  Serial.printf("👶 Policy for Child ID: %s, Age: %d\n", childId.c_str(), age);
  
  if (doc.containsKey("filters")) {
    JsonObject filters = doc["filters"];
    String contentLevel = filters["content"] | "moderate";
    
    Serial.printf("🔒 Content filtering level: %s\n", contentLevel.c_str());
    
    // Handle blocked topics array
    if (filters.containsKey("blocked_topics")) {
      JsonArray blockedTopics = filters["blocked_topics"];
      Serial.printf("🚫 Blocked topics (%d): ", blockedTopics.size());
      
      for (JsonVariant topic : blockedTopics) {
        Serial.printf("%s ", topic.as<String>().c_str());
      }
      Serial.println();
    }
    
    // Store policy settings for content filtering
    // updateContentPolicy(childId, age, contentLevel, blockedTopics); // Implement in child_safety_service
  }
  
  // Visual feedback for policy update
  setLEDColor("blue", 50);
  delay(500);
  clearLEDs();
}

/**
 * Handle Security Alert message from server
 * Format: {"type": "alert", "severity": "high", "code": "pii_detected", "message": "Sensitive info detected"}
 */
void handleSecurityAlert(DynamicJsonDocument& doc) {
  String severity = doc["severity"] | "medium";
  String code = doc["code"] | "unknown";
  String message = doc["message"] | "Security alert";
  
  Serial.printf("🚨 SECURITY ALERT [%s] %s: %s\n", severity.c_str(), code.c_str(), message.c_str());
  
  // Handle different alert severities
  if (severity == "critical") {
    // Critical alerts - immediate action required
    Serial.println("🔥 CRITICAL SECURITY ALERT - Taking immediate action");
    
    // Flash red LEDs rapidly
    for (int i = 0; i < 10; i++) {
      setLEDColor("red", 100);
      delay(100);
      clearLEDs();
      delay(100);
    }
    
    // Log to security system
    logSecurityEvent("Critical server alert: " + code, 4);
    
    // Stop audio processing temporarily
    // stopAudioProcessing(); // Implement in audio_handler.cpp
    
  } else if (severity == "high") {
    // High alerts - significant security concern
    Serial.println("⚠️ HIGH SECURITY ALERT - Enhanced monitoring");
    
    // Flash orange LEDs
    for (int i = 0; i < 5; i++) {
      setLEDColor("orange", 80);
      delay(200);
      clearLEDs();
      delay(200);
    }
    
    logSecurityEvent("High server alert: " + code, 3);
    
  } else if (severity == "medium") {
    // Medium alerts - standard security notification
    Serial.println("ℹ️ MEDIUM SECURITY ALERT - Standard monitoring");
    
    setLEDColor("yellow", 60);
    delay(1000);
    clearLEDs();
    
    logSecurityEvent("Medium server alert: " + code, 2);
    
  } else {
    // Low alerts - informational
    Serial.println("💡 LOW SECURITY ALERT - Informational");
    
    setLEDColor("blue", 40);
    delay(500);
    clearLEDs();
    
    logSecurityEvent("Low server alert: " + code, 1);
  }
  
  // Handle specific alert codes
  if (code == "pii_detected") {
    Serial.println("🔐 PII detected - activating enhanced privacy mode");
    // activatePrivacyMode(); // Implement in child_safety_service
    
  } else if (code == "inappropriate_content") {
    Serial.println("🚫 Inappropriate content detected - updating filters");
    // updateContentFilters(); // Implement in child_safety_service
    
  } else if (code == "rate_limit_exceeded") {
    Serial.println("🐌 Rate limit exceeded - reducing request frequency");
    // adjustRequestRate(); // Implement rate limiting
    
  } else if (code == "authentication_required") {
    Serial.println("🔑 Authentication required - triggering re-authentication");
    // Force device re-authentication
    authenticateDevice();
  }
}

/**
 * Handle JWT Authentication Response (auth/ok or auth/error)
 */
void handleAuthenticationResponse(DynamicJsonDocument& doc, bool success) {
  String type = doc["type"];
  
  if (success && type == "auth/ok") {
    Serial.println("✅ WebSocket JWT authentication successful");
    
    // Extract new token expiry if provided
    if (doc.containsKey("exp_in_sec")) {
      uint32_t expiresInSec = doc["exp_in_sec"];
      Serial.printf("🔄 Token refreshed, expires in %u seconds\n", expiresInSec);
      
      // Update JWT Manager with new expiry
      JWTManager* jwtManager = JWTManager::getInstance();
      if (jwtManager) {
        jwtManager->handleRefreshResponse(doc.as<String>());
      }
    }
    
    // Show success indication
    setLEDColor("green", 80);
    delay(300);
    clearLEDs();
    
  } else if (!success && type == "auth/error") {
    String reason = doc["reason"] | "Authentication failed";
    Serial.printf("❌ WebSocket JWT authentication failed: %s\n", reason.c_str());
    
    // Show error indication
    setLEDColor("red", 80);
    delay(300);
    clearLEDs();
    
    // Trigger re-authentication
    Serial.println("🔄 Triggering device re-authentication due to WebSocket auth failure");
    authenticateDevice();
  }
}

/**
 * Handle incoming binary audio frames from server
 * Direct PCM 16kHz mono s16le audio data
 */
void handleIncomingAudioFrame(uint8_t* audioData, size_t length) {
  Serial.printf("🎵 Processing incoming audio frame: %d bytes\n", length);
  
  // Validate audio frame format
  if (length == 4096) {
    Serial.println("✅ Audio frame size matches expected 4096B PCM chunk");
  } else {
    Serial.printf("⚠️ Unexpected audio frame size: %d bytes (expected 4096)\n", length);
  }
  
  // Show audio activity
  setLEDColor("cyan", 60);
  
  // Process PCM audio data directly
  // playPCMAudio(audioData, length, 16000, 1); // Implement in audio_handler.cpp
  
  // For now, acknowledge receipt
  Serial.printf("🔊 Playing %d bytes of PCM audio from server\n", length);
  
  // Clear LED after processing
  delay(50); // Brief audio indicator
  clearLEDs();
}

/**
 * Handle JWT refresh messages for WebSocket authentication
 */
bool handleJWTRefreshMessage(const String& refreshMessage) {
  if (!isConnected) {
    Serial.println("❌ Cannot send JWT refresh - WebSocket not connected");
    return false;
  }
  
  Serial.printf("🔄 Sending JWT refresh via WebSocket: %s\n", refreshMessage.c_str());
  
  // Send JWT refresh request as text message
  bool success = webSocket.sendTXT(refreshMessage.c_str());
  
  if (success) {
    Serial.println("✅ JWT refresh request sent via WebSocket");
  } else {
    Serial.println("❌ Failed to send JWT refresh request via WebSocket");
  }
  
  return success;
}

void sendButtonEvent() {
  if (!isConnected) {
    Serial.println("❌ Cannot send button event - WebSocket not connected");
    return;
  }
  
  DynamicJsonDocument doc(512);
  doc["type"] = "button_pressed";
  doc["deviceId"] = getCurrentDeviceId();
  doc["timestamp"] = millis();
  
  String message;
  serializeJson(doc, message);
  
  if (webSocket.sendTXT(message)) {
    Serial.println("✅ Button event sent");
  } else {
    Serial.println("❌ Failed to send button event");
  }
}
