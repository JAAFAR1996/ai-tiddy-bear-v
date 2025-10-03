#ifndef SYSTEM_MONITOR_H
#define SYSTEM_MONITOR_H

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <esp_system.h>

/**
 * Production System Monitor for AI Teddy Bear ESP32
 * 
 * Features:
 * - Brownout detection for power stability
 * - Task Watchdog Timer (WDT) for critical tasks
 * - Heap monitoring with 40KB threshold for audio
 * - System health checks and recovery
 * - Reset reason tracking
 * 
 * Critical for production deployment and 2-hour stability test
 */

// System monitor initialization
bool initProductionSystemMonitor();
void cleanupSystemMonitor();

// Watchdog Timer management
bool addTaskToWDT(TaskHandle_t taskHandle, const char* taskName);
bool removeTaskFromWDT(TaskHandle_t taskHandle, const char* taskName);
void feedWDT(); // For main loop only

// Task-specific WDT feeding (call from within each task)
void feedAudioTaskWDT();
void feedWebSocketTaskWDT();

// Critical task registration
void registerAudioTaskWDT(TaskHandle_t taskHandle);
void registerWebSocketTaskWDT(TaskHandle_t taskHandle);

// System health monitoring
void performSystemHealthCheck();
bool isSystemHealthyForAudio();
void handleSystemMonitor();

// Recovery and diagnostics
void triggerSystemRecovery(const char* reason);
const char* getResetReasonString(esp_reset_reason_t reason);

#endif // SYSTEM_MONITOR_H