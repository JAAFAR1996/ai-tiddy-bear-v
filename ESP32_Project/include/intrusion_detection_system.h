#ifndef INTRUSION_DETECTION_SYSTEM_H
#define INTRUSION_DETECTION_SYSTEM_H

#include <Arduino.h>

// IDS initialization and control
bool initIntrusionDetectionSystem();
void startIntrusionDetection();
void stopIntrusionDetection();
void cleanupIntrusionDetectionSystem();

// Threat detection and handling
void reportSuspiciousActivity(const char* description, int severity);
bool isSystemLocked();

// Individual threat checks (exposed for testing)
bool checkBruteForceAttempts();
bool checkMemoryCorruption();
bool checkHardwareTampering();
bool checkUnauthorizedAccess();
bool checkDebugInterfaceAccess();
bool checkTimeManipulation();

// Threat handling functions
void handleHighSeverityThreat(const char* threatName, int severity);
void handleMediumSeverityThreat(const char* threatName, int severity);
void handleLowSeverityThreat(const char* threatName, int severity);
void lockdownSystem();

// Statistics and monitoring
void printIDSStatistics();

#endif