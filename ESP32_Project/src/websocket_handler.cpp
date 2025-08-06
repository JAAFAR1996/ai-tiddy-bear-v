#include "websocket_handler.h"
#include "hardware.h"
#include "sensors.h"
#include "audio_handler.h"
#include "wifi_manager.h"
#include "config.h"
#include <WiFi.h>
#include <base64.h>

WebSocketsClient webSocket;
bool isConnected = false;

void initWebSocket() {
  Serial.println("🌐 Initializing WebSocket...");
  
  // استخدام إعدادات السيرفر من deviceConfig
  String wsProtocol = deviceConfig.ssl_enabled ? "wss" : "ws";
  int wsPort = deviceConfig.ssl_enabled ? 443 : deviceConfig.server_port;
  const char* wsPath = DEFAULT_WEBSOCKET_PATH;
  
  // إعداد SSL إذا كان مفعلاً
  if (deviceConfig.ssl_enabled) {
    webSocket.beginSSL(deviceConfig.server_host, wsPort, wsPath);
  } else {
    webSocket.begin(deviceConfig.server_host, wsPort, wsPath);
  }
  
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(RECONNECT_INTERVAL);
  
  Serial.printf("🔗 Connecting to: %s://%s:%d%s\n", 
                wsProtocol.c_str(), deviceConfig.server_host, wsPort, wsPath);
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("❌ WebSocket Disconnected");
      isConnected = false;
      setLEDColor("red", 50);
      delay(500);
      clearLEDs();
      break;
      
    case WStype_CONNECTED:
      Serial.printf("✅ WebSocket Connected to: %s\n", payload);
      isConnected = true;
      sendHandshake();
      playWelcomeAnimation();
      break;
      
    case WStype_TEXT:
      Serial.printf("📨 Received: %s\n", payload);
      handleIncomingMessage(String((char*)payload));
      break;
      
    case WStype_ERROR:
      Serial.printf("❌ WebSocket Error\n");
      break;
      
    default:
      break;
  }
}

void handleIncomingMessage(String message) {
  DynamicJsonDocument doc(512);  // Reduced from 1024
  DeserializationError error = deserializeJson(doc, message);
  
  if (error) {
    Serial.printf("❌ JSON Parse Error: %s\n", error.c_str());
    sendResponse("error", "Invalid JSON format");
    return;
  }
  
  String type = doc["type"] | "";
  String requestId = doc["id"] | "";
  JsonObject params = doc["params"];
  
  Serial.printf("🎯 Command: %s\n", type.c_str());
  
  if (type == "handshake") {
    sendHandshake();
  }
  else if (type == "led_control") {
    handleLEDCommand(params);
    sendResponse("ok", "LED controlled", requestId);
  }
  else if (type == "motor_control") {
    handleServoCommand(params);
    sendResponse("ok", "Servo controlled", requestId);
  }
  else if (type == "audio_play") {
    handleAudioCommand(params);
    sendResponse("ok", "Audio played", requestId);
  }
  else if (type == "animation") {
    handleAnimationCommand(params);
    sendResponse("ok", "Animation played", requestId);
  }
  else if (type == "status_check") {
    handleStatusRequest();
  }
  else if (type == "sensor_read") {
    sendSensorData();
  }
  else if (type == "audio_response") {
    handleAudioResponse(params);
  }
  else {
    sendResponse("error", "Unknown command: " + type, requestId);
  }
}

void sendHandshake() {
  DynamicJsonDocument doc(512);
  doc["type"] = "handshake";
  doc["device_id"] = DEVICE_ID;
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["timestamp"] = millis();
  doc["protocol_version"] = "1.0";
  
  JsonArray capabilities = doc.createNestedArray("capabilities");
  capabilities.add("led_control");
  capabilities.add("motor_control");
  capabilities.add("audio_play");
  capabilities.add("animation");
  capabilities.add("sensor_read");
  capabilities.add("audio_recording");
  capabilities.add("audio_playback");
  
  JsonObject hardware = doc.createNestedObject("hardware");
  hardware["leds"] = NUM_LEDS;
  hardware["servo"] = true;
  hardware["speaker"] = true;
  hardware["button"] = true;
  hardware["microphone"] = true;
  hardware["i2s_audio"] = true;
  
  String message;
  serializeJson(doc, message);
  webSocket.sendTXT(message);
  
  Serial.println("🤝 Handshake sent");
}

void sendSensorData() {
  DynamicJsonDocument doc(512);
  doc["type"] = "sensor_data";
  doc["device_id"] = DEVICE_ID;
  doc["timestamp"] = millis();
  
  SensorData data = readAllSensors();
  JsonObject sensorData = doc.createNestedObject("data");
  sensorData["button_pressed"] = data.buttonPressed;
  sensorData["wifi_strength"] = data.wifiStrength;
  sensorData["uptime"] = data.uptime;
  sensorData["free_heap"] = data.freeHeap;
  sensorData["servo_angle"] = headServo.read();
  
  String message;
  serializeJson(doc, message);
  webSocket.sendTXT(message);
  
  Serial.println("📊 Sensor data sent");
}

void sendButtonEvent() {
  if (!isConnected) return;
  
  DynamicJsonDocument doc(256);
  doc["type"] = "button_press";
  doc["device_id"] = DEVICE_ID;
  doc["timestamp"] = millis();
  doc["button_id"] = "main_button";
  
  String message;
  serializeJson(doc, message);
  webSocket.sendTXT(message);
  
  Serial.println("🔘 Button event sent");
}

void sendHeartbeat() {
  if (!isConnected) return;
  
  DynamicJsonDocument doc(256);
  doc["type"] = "heartbeat";
  doc["device_id"] = DEVICE_ID;
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
  doc["device_id"] = DEVICE_ID;
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
  doc["device_id"] = DEVICE_ID;
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

void handleServoCommand(JsonObject params) {
  String direction = params["direction"] | "center";
  int speed = params["speed"] | 50;
  
  moveServo(direction, speed);
}

void handleAudioCommand(JsonObject params) {
  String audioType = params["file"] | "default";
  int volume = params["volume"] | 50;
  
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

void reconnectWebSocket() {
  if (!isConnected && WiFi.status() == WL_CONNECTED) {
    Serial.println("🔄 Attempting WebSocket reconnection...");
    webSocket.disconnect();
    delay(1000);
    initWebSocket();
  }
}

String createMessage(String type, JsonObject data) {
  DynamicJsonDocument doc(512);
  doc["type"] = type;
  doc["device_id"] = DEVICE_ID;
  doc["timestamp"] = millis();
  
  if (!data.isNull()) {
    doc["data"] = data;
  }
  
  String message;
  serializeJson(doc, message);
  return message;
}

void handleAudioResponse(JsonObject params) {
  // Handle audio response from server
  String audioData = params["audio_data"] | "";
  String format = params["format"] | "wav";
  
  if (audioData.length() > 0) {
    Serial.println("🔊 Received audio response: " + String(audioData.length()) + " bytes");
    
    // Decode base64 audio data and play it
    if (decodeAndPlayAudio(audioData, format)) {
      Serial.println("✅ Audio played successfully");
      // Play success tone
      playTone(FREQ_HAPPY, 200);
    } else {
      Serial.println("❌ Failed to play audio");
      // Play error tone
      playTone(FREQ_ERROR, 300);
      // Fallback to happy tone for user experience
      delay(100);
      playTone(FREQ_HAPPY, 500);
    }
  }
}

// Decode base64 audio and attempt playback
bool decodeAndPlayAudio(const String& base64Audio, const String& format) {
  if (base64Audio.length() == 0) return false;
  
  Serial.println("🎵 Decoding " + format + " audio: " + String(base64Audio.length()) + " chars");
  
  // Calculate decoded size (base64 is ~33% larger than binary)
  size_t decodedSize = (base64Audio.length() * 3) / 4;
  
  // Allocate buffer for decoded audio (with safety margin)
  uint8_t* audioBuffer = (uint8_t*)malloc(decodedSize + 16);
  if (audioBuffer == nullptr) {
    Serial.println("❌ Failed to allocate audio buffer");
    return false;
  }
  
  // Simple base64 decode implementation for ESP32
  size_t actualSize = base64_decode(base64Audio.c_str(), base64Audio.length(), audioBuffer, decodedSize);
  
  if (actualSize == 0) {
    Serial.println("❌ Base64 decode failed");
    free(audioBuffer);
    return false;
  }
  
  Serial.println("✅ Decoded " + String(actualSize) + " bytes of audio data");
  
  // Attempt to play audio based on format
  bool success = false;
  
  if (format == "wav" || format == "audio/wav") {
    success = playWAVAudio(audioBuffer, actualSize);
  } else if (format == "mp3" || format == "audio/mp3") {
    success = playMP3Audio(audioBuffer, actualSize);
  } else {
    Serial.println("⚠️  Unsupported audio format: " + format + ", attempting WAV playback");
    success = playWAVAudio(audioBuffer, actualSize);
  }
  
  free(audioBuffer);
  return success;
}

// Simple base64 decode function
size_t base64_decode(const char* input, size_t inputLen, uint8_t* output, size_t outputLen) {
  const char* chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  size_t outputPos = 0;
  uint32_t buffer = 0;
  int bufferBits = 0;
  
  for (size_t i = 0; i < inputLen && outputPos < outputLen; i++) {
    char c = input[i];
    if (c == '=') break; // Padding
    
    // Find character position
    int value = -1;
    for (int j = 0; j < 64; j++) {
      if (chars[j] == c) {
        value = j;
        break;
      }
    }
    
    if (value == -1) continue; // Invalid character, skip
    
    buffer = (buffer << 6) | value;
    bufferBits += 6;
    
    if (bufferBits >= 8) {
      output[outputPos++] = (buffer >> (bufferBits - 8)) & 0xFF;
      bufferBits -= 8;
    }
  }
  
  return outputPos;
}

// Play WAV audio using I2S or DAC
bool playWAVAudio(uint8_t* audioData, size_t length) {
  // Basic WAV header validation
  if (length < 44) {
    Serial.println("❌ Audio data too small for WAV format");
    return false;
  }
  
  // Check WAV header
  if (memcmp(audioData, "RIFF", 4) != 0 || memcmp(audioData + 8, "WAVE", 4) != 0) {
    Serial.println("❌ Invalid WAV header");
    return false;
  }
  
  Serial.println("🎵 Playing WAV audio...");
  
  // Skip WAV header (44 bytes) and play PCM data
  uint8_t* pcmData = audioData + 44;
  size_t pcmLength = length - 44;
  
  // Use ESP32's built-in DAC for simple audio output
  return playPCMAudio(pcmData, pcmLength);
}

// Play MP3 audio (simplified implementation)
bool playMP3Audio(uint8_t* audioData, size_t length) {
  Serial.println("⚠️  MP3 playback not fully implemented, converting to simple tones");
  
  // For now, analyze MP3 data and generate corresponding tones
  // This is a simplified approach for the ESP32 teddy bear
  
  // Generate pleasant melody based on audio data size
  int numTones = min((int)(length / 1000), 8); // Up to 8 tones
  
  for (int i = 0; i < numTones; i++) {
    int frequency = 220 + (audioData[i * 100 % length] % 200); // Generate frequency from data
    int duration = 100 + (audioData[i * 150 % length] % 100);  // Generate duration from data
    
    playTone(frequency, duration);
    delay(50); // Brief pause between tones
  }
  
  return true;
}

// Play PCM audio using DAC
bool playPCMAudio(uint8_t* pcmData, size_t length) {
  Serial.println("🎵 Playing PCM audio on DAC...");
  
  // ESP32 DAC output on GPIO25 and GPIO26
  // For simplicity, use GPIO25 (DAC1)
  
  // Calculate playback timing (assume 8kHz sample rate for speech)
  const int sampleRate = 8000;
  const int delayMicros = 1000000 / sampleRate; // Microseconds per sample
  
  // Play audio samples
  for (size_t i = 0; i < length && i < 8000; i += 2) { // Limit to ~1 second max
    // Convert 16-bit PCM to 8-bit for DAC
    uint16_t sample16 = (pcmData[i] | (pcmData[i+1] << 8));
    uint8_t sample8 = (sample16 >> 8) & 0xFF;
    
    // Output to DAC (0-255 range)
    dacWrite(25, sample8);
    
    delayMicroseconds(delayMicros);
  }
  
  // Silence the DAC
  dacWrite(25, 128); // Mid-point for silence
  
  Serial.println("✅ PCM audio playback completed");
  return true;
}

void sendAudioData(uint8_t* audioData, size_t length) {
  if (!isConnected || audioData == nullptr || length == 0) return;
  
  // Send audio in smaller chunks to avoid memory issues
  const size_t chunkSize = 1024;  // Send 1KB chunks
  size_t totalChunks = (length + chunkSize - 1) / chunkSize;
  
  for (size_t i = 0; i < totalChunks; i++) {
    size_t offset = i * chunkSize;
    size_t currentChunkSize = min(chunkSize, length - offset);
    
    // Convert chunk to base64
    String base64Chunk = base64::encode(audioData + offset, currentChunkSize);
    
    DynamicJsonDocument doc(256 + base64Chunk.length());
    doc["type"] = "audio_chunk";
    doc["device_id"] = DEVICE_ID;
    doc["timestamp"] = millis();
    doc["chunk_index"] = i;
    doc["total_chunks"] = totalChunks;
    doc["format"] = "wav";
    doc["sample_rate"] = 16000;
    doc["channels"] = 1;
    doc["audio_data"] = base64Chunk;
    
    String message;
    serializeJson(doc, message);
    webSocket.sendTXT(message);
    
    delay(10);  // Small delay between chunks
  }
  
  Serial.printf("🎤 Audio data sent in %d chunks (%d bytes total)\n", totalChunks, length);
}

void logMessage(String direction, String message) {
  Serial.printf("[%s] %s\n", direction.c_str(), message.c_str());
}