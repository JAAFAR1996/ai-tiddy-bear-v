#include "sensors.h"
#include <WiFi.h>

void initSensors() {
  Serial.println("📊 Initializing sensors...");
  
  // Initialize button pin
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  Serial.println("✅ Basic sensors initialized!");
}

SensorData readAllSensors() {
  SensorData data;
  
  data.buttonPressed = isButtonPressed();
  data.wifiStrength = getWiFiStrength();
  data.uptime = getUptime();
  data.freeHeap = getFreeHeap();
  
  return data;
}

bool isButtonPressed() {
  return digitalRead(BUTTON_PIN) == LOW;
}

int getWiFiStrength() {
  if (WiFi.status() == WL_CONNECTED) {
    return WiFi.RSSI();
  }
  return -100; // No connection
}

unsigned long getUptime() {
  return millis();
}

int getFreeHeap() {
  return ESP.getFreeHeap();
}

String sensorsToJson() {
  SensorData data = readAllSensors();
  
  String json = "{";
  json += "\"button_pressed\":" + String(data.buttonPressed ? "true" : "false") + ",";
  json += "\"wifi_strength\":" + String(data.wifiStrength) + ",";
  json += "\"uptime\":" + String(data.uptime) + ",";
  json += "\"free_heap\":" + String(data.freeHeap);
  json += "}";
  
  return json;
}

void printSensorData(SensorData data) {
  Serial.println("=== 📊 Sensor Data ===");
  Serial.printf("Button: %s\n", data.buttonPressed ? "PRESSED" : "RELEASED");
  Serial.printf("WiFi: %d dBm\n", data.wifiStrength);
  Serial.printf("Uptime: %lu ms\n", data.uptime);
  Serial.printf("Free Heap: %d bytes\n", data.freeHeap);
  Serial.println("=====================");
}