#ifndef SENSORS_H
#define SENSORS_H

#include <Arduino.h>
#include "config.h"

// Basic sensor data structure (only what you have)
struct SensorData {
  bool buttonPressed;
  int wifiStrength;
  unsigned long uptime;
  int freeHeap;
};

// Basic sensor functions
void initSensors();
SensorData readAllSensors();
bool isButtonPressed();
int getWiFiStrength();
unsigned long getUptime();
int getFreeHeap();

// Sensor utilities
String sensorsToJson();
void printSensorData(SensorData data);

#endif