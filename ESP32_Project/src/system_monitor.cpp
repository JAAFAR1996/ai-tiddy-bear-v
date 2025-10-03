#include <Arduino.h>  // لـ millis/Serial/delay
#include "system_monitor.h"
#include "config.h"
#include <esp_task_wdt.h>
#include <esp_system.h>
// Prevent CONFIG_LOG_DEFAULT_LEVEL redefinition warning
#ifdef CONFIG_LOG_DEFAULT_LEVEL
#undef CONFIG_LOG_DEFAULT_LEVEL
#endif
#include <esp_log.h>
#include <esp_err.h>  // esp_err_to_name
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

static const char* TAG = "SYS_MON";

// WDT handles for critical tasks
static TaskHandle_t audioTaskHandle = nullptr;
static TaskHandle_t websocketTaskHandle = nullptr;
static TaskHandle_t mainLoopTaskHandle = nullptr;

// System monitor state
static bool systemMonitorInitialized = false;
static unsigned long lastWDTFeed = 0;
static unsigned long lastHeapCheck = 0;

/**
 * Initialize production system monitoring
 * - Enable brownout detection at 2.43V (production safe)
 * - Configure task watchdog for critical tasks
 * - Set up system health monitoring
 */
bool initProductionSystemMonitor() {
    if (systemMonitorInitialized) {
        return true;
    }
    
    Serial.println("⚡ Initializing production system monitor...");
    
    // 1. Configure Brownout Detection (via Kconfig, not runtime)
#if defined(CONFIG_BROWNOUT_DET) || defined(CONFIG_ESP_BROWNOUT_DET) || defined(CONFIG_ESP_SYSTEM_BROWNOUT)
    // مفعل من الإعدادات
    Serial.println("⚡ Brownout detection enabled (Kconfig)");
#else
    Serial.println("⚠️ Brownout control not available at runtime on this build");
#endif
    
    // 2. Configure Task Watchdog Timer for critical tasks
    uint32_t wdt_sec = max(1U, (uint32_t)(WATCHDOG_TIMEOUT / 1000)); // Ensure minimum 1 second
    esp_err_t wdt_result = esp_task_wdt_init(wdt_sec, true);
    if (wdt_result != ESP_OK && wdt_result != ESP_ERR_INVALID_STATE) {
        Serial.printf("❌ Task WDT init failed: %s\n", esp_err_to_name(wdt_result));
        return false;
    }
    
    // Add current task (setup/main) to WDT
    mainLoopTaskHandle = xTaskGetCurrentTaskHandle();
    wdt_result = esp_task_wdt_add(mainLoopTaskHandle);
    if (wdt_result == ESP_OK) {
        Serial.printf("✅ Main loop added to WDT (timeout: %ds)\n", WATCHDOG_TIMEOUT / 1000);
    } else {
        Serial.printf("⚠️ Failed to add main loop to WDT: %s\n", esp_err_to_name(wdt_result));
    }
    
    // 3. Set up system health monitoring intervals
    lastWDTFeed = millis();
    lastHeapCheck = millis();
    
    systemMonitorInitialized = true;
    Serial.println("✅ Production system monitor initialized");
    
    return true;
}

/**
 * Add critical task to watchdog monitoring
 */
bool addTaskToWDT(TaskHandle_t taskHandle, const char* taskName) {
    if (!systemMonitorInitialized || taskHandle == nullptr) {
        return false;
    }
    
    esp_err_t result = esp_task_wdt_add(taskHandle);
    if (result == ESP_OK) {
        Serial.printf("✅ Task '%s' added to WDT monitoring\n", taskName);
        return true;
    } else {
        Serial.printf("❌ Failed to add task '%s' to WDT: %s\n", taskName, esp_err_to_name(result));
        return false;
    }
}

/**
 * Remove task from watchdog monitoring
 */
bool removeTaskFromWDT(TaskHandle_t taskHandle, const char* taskName) {
    if (!systemMonitorInitialized || taskHandle == nullptr) {
        return false;
    }
    
    esp_err_t result = esp_task_wdt_delete(taskHandle);
    if (result == ESP_OK) {
        Serial.printf("✅ Task '%s' removed from WDT monitoring\n", taskName);
        return true;
    } else {
        Serial.printf("❌ Failed to remove task '%s' from WDT: %s\n", taskName, esp_err_to_name(result));
        return false;
    }
}

/**
 * Feed the watchdog timer (call from critical tasks)
 * NOTE: Each task must call this from within its own context
 */
void feedWDT() {
    if (!systemMonitorInitialized) {
        return;
    }
    
    esp_task_wdt_reset(); // Feeds current task only
    lastWDTFeed = millis(); // Track main loop feed time
    
    // Only log WDT feed in development mode
#ifndef PRODUCTION_BUILD
    static unsigned long lastWDTLog = 0;
    if (millis() - lastWDTLog > 10000) { // Log every 10 seconds in dev
        Serial.println("🐕 Main loop WDT fed (development)");
        lastWDTLog = millis();
    }
#endif
}

/**
 * Feed WDT from within audio task (call from audio task context)
 */
void feedAudioTaskWDT() {
    esp_task_wdt_reset(); // Feeds current (audio) task
}

/**
 * Feed WDT from within WebSocket task (call from WebSocket task context)  
 */
void feedWebSocketTaskWDT() {
    esp_task_wdt_reset(); // Feeds current (WebSocket) task
}

/**
 * Register audio task for WDT monitoring
 * NOTE: Audio task must call esp_task_wdt_add(NULL) once at startup
 * and feedAudioTaskWDT() regularly (every ≤ WATCHDOG_TIMEOUT/2)
 */
void registerAudioTaskWDT(TaskHandle_t taskHandle) {
    audioTaskHandle = taskHandle;
    // Task should add itself: esp_task_wdt_add(NULL) from within task
    Serial.println("📝 Audio task registered for WDT (task must self-add)");
}

/**
 * Register WebSocket task for WDT monitoring
 * NOTE: WebSocket task must call esp_task_wdt_add(NULL) once at startup
 * and feedWebSocketTaskWDT() regularly (every ≤ WATCHDOG_TIMEOUT/2)
 */
void registerWebSocketTaskWDT(TaskHandle_t taskHandle) {
    websocketTaskHandle = taskHandle;
    // Task should add itself: esp_task_wdt_add(NULL) from within task
    Serial.println("📝 WebSocket task registered for WDT (task must self-add)");
}

/**
 * System health check with heap monitoring
 */
void performSystemHealthCheck() {
    unsigned long now = millis();
    
    // Check system health every 30 seconds
    if (now - lastHeapCheck > 30000) {
        lastHeapCheck = now;
        
        // Monitor free heap
        size_t freeHeap = ESP.getFreeHeap();
        size_t minFreeHeap = ESP.getMinFreeHeap();
        
        // Critical heap threshold for audio operations (40KB as specified)
        const size_t CRITICAL_HEAP_THRESHOLD = 40 * 1024; // 40KB
        
        if (freeHeap < CRITICAL_HEAP_THRESHOLD) {
            Serial.printf("🚨 CRITICAL: Low heap memory! Free: %d bytes (min: %d)\n", 
                         freeHeap, minFreeHeap);
            
#ifdef PRODUCTION_BUILD
            // In production, trigger controlled restart if heap is critically low
            if (freeHeap < 20 * 1024) { // 20KB emergency threshold
                Serial.println("💥 EMERGENCY: Heap exhaustion, restarting system");
                ESP.restart();
            }
#endif
        } else {
            // Normal heap logging (less frequent in production)
#ifdef PRODUCTION_BUILD
            static unsigned long lastHeapLog = 0;
            if (now - lastHeapLog > 300000) { // Log every 5 minutes in production
                Serial.printf("💾 Heap OK: %d KB free (min: %d KB)\n", 
                             freeHeap / 1024, minFreeHeap / 1024);
                lastHeapLog = now;
            }
#else
            Serial.printf("💾 Heap status: %d KB free (min: %d KB)\n", 
                         freeHeap / 1024, minFreeHeap / 1024);
#endif
        }
        
        // Check main loop WDT health only
        if (now - lastWDTFeed > WATCHDOG_TIMEOUT * 2) {
            Serial.printf("⚠️ Main loop WDT feed overdue: %lu ms (timeout: %d ms)\n", 
                         now - lastWDTFeed, WATCHDOG_TIMEOUT);
        }
        
        // Log system uptime and reset reason
        esp_reset_reason_t resetReason = esp_reset_reason();
        const char* resetReasonStr = getResetReasonString(resetReason);
        
#ifndef PRODUCTION_BUILD
        Serial.printf("⏱️ Uptime: %lu ms, Last reset: %s\n", 
                     now, resetReasonStr);
#endif
    }
}

/**
 * Get reset reason as human-readable string
 */
const char* getResetReasonString(esp_reset_reason_t reason) {
    switch (reason) {
        case ESP_RST_POWERON:   return "Power-on reset";
        case ESP_RST_EXT:       return "External reset";
        case ESP_RST_SW:        return "Software reset";
        case ESP_RST_PANIC:     return "Exception/panic reset";
        case ESP_RST_INT_WDT:   return "Interrupt watchdog";
        case ESP_RST_TASK_WDT:  return "Task watchdog";
        case ESP_RST_WDT:       return "Other watchdogs";
        case ESP_RST_DEEPSLEEP: return "Deep sleep reset";
        case ESP_RST_BROWNOUT:  return "Brownout reset";
        case ESP_RST_SDIO:      return "SDIO reset";
        default:                return "Unknown reset";
    }
}

/**
 * Check if system is healthy for audio operations
 */
bool isSystemHealthyForAudio() {
    if (!systemMonitorInitialized) {
        return false;
    }
    
    // Check heap availability
    size_t freeHeap = ESP.getFreeHeap();
    const size_t AUDIO_HEAP_THRESHOLD = 40 * 1024; // 40KB as specified
    
    if (freeHeap < AUDIO_HEAP_THRESHOLD) {
        Serial.printf("⚠️ Insufficient heap for audio: %d KB (need: %d KB)\n", 
                     freeHeap / 1024, AUDIO_HEAP_THRESHOLD / 1024);
        return false;
    }
    
    // Check if WDT is being fed regularly
    unsigned long now = millis();
    if (now - lastWDTFeed > WATCHDOG_TIMEOUT / 2) {
        Serial.println("⚠️ WDT not fed recently, system may be unstable");
        return false;
    }
    
    return true;
}

/**
 * System monitor loop - call from main loop
 */
void handleSystemMonitor() {
    if (!systemMonitorInitialized) {
        return;
    }
    
    // Feed watchdog regularly from main loop
    feedWDT();
    
    // Perform periodic health checks
    performSystemHealthCheck();
}

/**
 * Emergency system recovery
 */
void triggerSystemRecovery(const char* reason) {
    Serial.printf("🚨 SYSTEM RECOVERY TRIGGERED: %s\n", reason);
    
    // Log the recovery reason
    Serial.printf("📊 System stats at recovery:\n");
    Serial.printf("  - Free heap: %d bytes\n", ESP.getFreeHeap());
    Serial.printf("  - Min free heap: %d bytes\n", ESP.getMinFreeHeap());
    Serial.printf("  - Uptime: %lu ms\n", millis());
    
    // Disable WDT to prevent reset during logging
    esp_task_wdt_deinit();
    
    // Give time for logging
    delay(1000);
    
    // Controlled restart
    Serial.println("🔄 Performing controlled system restart...");
    ESP.restart();
}

/**
 * Cleanup system monitor
 */
void cleanupSystemMonitor() {
    if (!systemMonitorInitialized) {
        return;
    }
    
    // Remove all tasks from WDT
    if (audioTaskHandle) {
        esp_task_wdt_delete(audioTaskHandle);
    }
    if (websocketTaskHandle) {
        esp_task_wdt_delete(websocketTaskHandle);
    }
    if (mainLoopTaskHandle) {
        esp_task_wdt_delete(mainLoopTaskHandle);
    }
    
    // Deinitialize WDT
    esp_task_wdt_deinit();
    
    systemMonitorInitialized = false;
    Serial.println("🧹 System monitor cleanup complete");
}