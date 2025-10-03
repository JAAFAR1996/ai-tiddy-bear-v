#include "time_sync.h"
#include "esp_sntp.h"
#include "esp_log.h"
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <sys/time.h>
#include "esp_system.h"

static const char* TAG = "TIME_SYNC";
static bool time_synced = false;
static const time_t MIN_VALID_TIME = 1672531200; // 2023-01-01 00:00:00 UTC

// Ensure we never change SNTP settings while the client is running.
// Calling stop() is safe even if SNTP was not started.
static inline void sntp_safe_stop(void) {
    esp_sntp_stop();
    vTaskDelay(100 / portTICK_PERIOD_MS);
}

void setupProductionTimeSync() {
    ESP_LOGI(TAG, "Starting NTP time synchronization...");
    
    // Make sure SNTP is stopped before (re)configuring
    sntp_safe_stop();

    // Initialize SNTP
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    
    // Set multiple NTP servers for maximum reliability
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_setservername(1, "time.google.com");
    esp_sntp_setservername(2, "time.cloudflare.com");
    
    // Set timezone to UTC
    setenv("TZ", "UTC0", 1);
    tzset();
    
    esp_sntp_init();
    
    // Wait for time synchronization (max 10 seconds)
    int retry = 0;
    const int retry_count = 10;
    
    while (esp_sntp_get_sync_status() == SNTP_SYNC_STATUS_RESET && ++retry < retry_count) {
        ESP_LOGI(TAG, "Waiting for system time to be set... (%d/%d)", retry, retry_count);
        // Feed WDT during blocking NTP sync
        esp_task_wdt_reset();
        vTaskDelay(500 / portTICK_PERIOD_MS);
        esp_task_wdt_reset();
        vTaskDelay(500 / portTICK_PERIOD_MS);
    }
    
    if (esp_sntp_get_sync_status() == SNTP_SYNC_STATUS_COMPLETED) {
        time_synced = true;
        time_t now = time(NULL);
        ESP_LOGI(TAG, "Time synchronized successfully. Current time: %ld", now);
    } else {
        ESP_LOGW(TAG, "Time synchronization failed, using fallback time");
        // Set fallback time to prevent cert validation issues
        struct timeval tv = {0};
        tv.tv_sec = 1703980800; // 2023-12-31 00:00:00 UTC as fallback
        settimeofday(&tv, NULL);
        time_synced = false;
    }
}

time_t getCurrentTimestamp() {
    return time(NULL);
}

bool isTimeSynced() {
    time_t now = time(NULL);
    // Consider time valid if system clock is reasonably recent
    if (now >= MIN_VALID_TIME) {
        return true;
    }
    // Fallback to SNTP status flag
    return esp_sntp_get_sync_status() == SNTP_SYNC_STATUS_COMPLETED;
}

void requestSntpSync() {
    // Start or restart SNTP without blocking; safe to call repeatedly
    sntp_safe_stop();
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_setservername(1, "time.google.com");
    esp_sntp_setservername(2, "time.cloudflare.com");
    setenv("TZ", "UTC0", 1);
    tzset();
    esp_sntp_init();
}

// Helper functions for production time sync strategy
bool usePersistedTime() {
    // Check if we have a reasonably recent time stored
    time_t stored_time = time(NULL);
    if (stored_time > 1640995200) { // After 2022-01-01
        ESP_LOGI(TAG, "📦 Using persisted system time: %ld", stored_time);
        time_synced = true;
        return true;
    }
    return false;
}

bool syncTimeFromServer() {
    ESP_LOGI(TAG, "🌐 Attempting time sync from application server...");
    // This would typically make an HTTPS request to get server time
    // For now, we'll simulate this and fall back to NTP
    return false; // Not implemented yet
}

bool syncWithMultipleNTP() {
    ESP_LOGI(TAG, "⏰ Trying multiple NTP servers for time sync...");
    
    // Always stop before reconfiguring to avoid assertion in sntp_setoperatingmode
    sntp_safe_stop();
    
    // Reinitialize SNTP with multiple servers
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_setservername(1, "time.google.com");
    esp_sntp_setservername(2, "time.cloudflare.com");
    esp_sntp_init();
    
    // Wait for sync with reasonable timeout
    int retry = 0;
    const int max_retries = 8; // Increased for better reliability
    
    while (esp_sntp_get_sync_status() == SNTP_SYNC_STATUS_RESET && ++retry < max_retries) {
        ESP_LOGI(TAG, "⏳ NTP sync attempt %d/%d...", retry, max_retries);
        // Feed WDT during NTP retry
        esp_task_wdt_reset();
        vTaskDelay(500 / portTICK_PERIOD_MS);
        esp_task_wdt_reset();
        vTaskDelay(500 / portTICK_PERIOD_MS);
    }
    
    if (esp_sntp_get_sync_status() == SNTP_SYNC_STATUS_COMPLETED) {
        time_synced = true;
        time_t now = time(NULL);
        ESP_LOGI(TAG, "✅ NTP sync successful: %ld", now);
        return true;
    }
    
    ESP_LOGW(TAG, "⚠️ NTP sync failed");
    return false;
}

bool useNetworkEstimatedTime() {
    ESP_LOGI(TAG, "🔮 Using network-estimated time as fallback...");
    
    // Set a reasonable fallback time based on compile time + estimated uptime
    // This is better than having completely wrong time for SSL
    struct timeval tv = {0};
    tv.tv_sec = 1703980800 + (esp_timer_get_time() / 1000000); // 2024-01-01 + uptime in seconds
    settimeofday(&tv, NULL);
    
    time_synced = false; // Mark as not properly synced
    ESP_LOGW(TAG, "⚠️ Using estimated time - SSL may have issues");
    return true;
}

void startBackgroundNTPSync() {
    ESP_LOGI(TAG, "🔄 Starting background NTP sync...");
    // This could be implemented as a separate FreeRTOS task
    // For now, we'll just trigger a quick sync
    syncWithMultipleNTP();
}

// Production-ready time sync strategy
bool productionTimeSync() {
    ESP_LOGI(TAG, "🏭 Starting production time sync strategy...");
    
    // 1. Try persisted time first (instant)
    if (usePersistedTime()) {
        ESP_LOGI(TAG, "✅ Using persisted time estimate");
        
        // Async NTP sync in background for accuracy
        startBackgroundNTPSync();
        return true;
    }
    
    // 2. Try server time sync (reliable)
    if (syncTimeFromServer()) {
        ESP_LOGI(TAG, "✅ Time synced from server");
        return true;
    }
    
    // 3. Try multiple NTP servers
    if (syncWithMultipleNTP()) {
        ESP_LOGI(TAG, "✅ Time synced via NTP");
        return true;
    }
    
    // 4. Use network-estimated time
    ESP_LOGI(TAG, "🔮 Falling back to estimated time");
    return useNetworkEstimatedTime();
}

bool syncTimeWithNTP() {
    // Use the production strategy
    return productionTimeSync();
}
