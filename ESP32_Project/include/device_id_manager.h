#ifndef DEVICE_ID_MANAGER_H
#define DEVICE_ID_MANAGER_H

#include <Arduino.h>

// Global device ID access
extern String deviceId;

// Function to get current device ID
String getCurrentDeviceId();

// Function to generate dynamic device ID
String generateDynamicDeviceId();

// Function to get current child ID
String getCurrentChildId();

#endif // DEVICE_ID_MANAGER_H