#include <Arduino.h>
#include "connection_stats.h"
#include "system_monitor.h"
#include <Preferences.h>
#include <esp_system.h>

static const char* TAG = "CONN_STATS";
static Preferences statsPrefs;

// Connection statistics
static ConnectionStats stats = {};
static bool statsInitialized = false;

/**
 * Initialize connection statistics tracking
 */
bool initConnectionStats() {
    if (statsInitialized) {
        return true;
    }
    
    // Open NVS for persistent stats
    if (!statsPrefs.begin("conn_stats", false)) {
        Serial.println("❌ Failed to open connection stats NVS");
        return false;
    }
    
    // Load existing stats
    loadConnectionStats();
    
    // Record current boot
    stats.totalBootCount++;
    stats.lastResetReason = esp_reset_reason();
    
    // Save updated stats
    saveConnectionStats();
    
    // Log boot information
    logBootInformation();
    
    statsInitialized = true;
    Serial.println("✅ Connection statistics initialized");
    return true;
}

/**
 * Load connection statistics from NVS
 */
void loadConnectionStats() {
    stats.totalBootCount = statsPrefs.getUInt("boot_count", 0);
    stats.wifiConnectAttempts = statsPrefs.getUInt("wifi_attempts", 0);
    stats.wifiConnectSuccesses = statsPrefs.getUInt("wifi_success", 0);
    stats.wifiDisconnections = statsPrefs.getUInt("wifi_disconn", 0);
    stats.websocketConnectAttempts = statsPrefs.getUInt("ws_attempts", 0);
    stats.websocketConnectSuccesses = statsPrefs.getUInt("ws_success", 0);
    stats.websocketDisconnections = statsPrefs.getUInt("ws_disconn", 0);
    stats.jwtRefreshAttempts = statsPrefs.getUInt("jwt_attempts", 0);
    stats.jwtRefreshSuccesses = statsPrefs.getUInt("jwt_success", 0);
    stats.systemRecoveries = statsPrefs.getUInt("recoveries", 0);
    stats.lastResetReason = (esp_reset_reason_t)statsPrefs.getUChar("last_reset", ESP_RST_UNKNOWN);
}

/**
 * Save connection statistics to NVS
 */
void saveConnectionStats() {
    if (!statsInitialized) return;
    
    statsPrefs.putUInt("boot_count", stats.totalBootCount);
    statsPrefs.putUInt("wifi_attempts", stats.wifiConnectAttempts);
    statsPrefs.putUInt("wifi_success", stats.wifiConnectSuccesses);
    statsPrefs.putUInt("wifi_disconn", stats.wifiDisconnections);
    statsPrefs.putUInt("ws_attempts", stats.websocketConnectAttempts);
    statsPrefs.putUInt("ws_success", stats.websocketConnectSuccesses);
    statsPrefs.putUInt("ws_disconn", stats.websocketDisconnections);
    statsPrefs.putUInt("jwt_attempts", stats.jwtRefreshAttempts);
    statsPrefs.putUInt("jwt_success", stats.jwtRefreshSuccesses);
    statsPrefs.putUInt("recoveries", stats.systemRecoveries);
    statsPrefs.putUChar("last_reset", (uint8_t)stats.lastResetReason);
    
    // Auto-commit
    statsPrefs.end();
    statsPrefs.begin("conn_stats", false);
}

/**
 * Record WiFi connection attempt
 */
void recordWiFiAttempt(bool success) {
    if (!statsInitialized) return;
    
    stats.wifiConnectAttempts++;
    if (success) {
        stats.wifiConnectSuccesses++;
    }
    
    saveConnectionStats();
    
#ifndef PRODUCTION_BUILD
    Serial.printf("📊 WiFi attempt %s: %u/%u (%.1f%%)\n", 
                  success ? "SUCCESS" : "FAILED",
                  stats.wifiConnectSuccesses, stats.wifiConnectAttempts,
                  (float)stats.wifiConnectSuccesses / stats.wifiConnectAttempts * 100.0);
#endif
}

/**
 * Record WiFi disconnection
 */
void recordWiFiDisconnection() {
    if (!statsInitialized) return;
    
    stats.wifiDisconnections++;
    saveConnectionStats();
    
#ifndef PRODUCTION_BUILD
    Serial.printf("📊 WiFi disconnections: %u\n", stats.wifiDisconnections);
#endif
}

/**
 * Record WebSocket connection attempt
 */
void recordWebSocketAttempt(bool success) {
    if (!statsInitialized) return;
    
    stats.websocketConnectAttempts++;
    if (success) {
        stats.websocketConnectSuccesses++;
    }
    
    saveConnectionStats();
    
#ifndef PRODUCTION_BUILD
    Serial.printf("📊 WebSocket attempt %s: %u/%u (%.1f%%)\n", 
                  success ? "SUCCESS" : "FAILED",
                  stats.websocketConnectSuccesses, stats.websocketConnectAttempts,
                  (float)stats.websocketConnectSuccesses / stats.websocketConnectAttempts * 100.0);
#endif
}

/**
 * Record WebSocket disconnection
 */
void recordWebSocketDisconnection() {
    if (!statsInitialized) return;
    
    stats.websocketDisconnections++;
    saveConnectionStats();
    
#ifndef PRODUCTION_BUILD
    Serial.printf("📊 WebSocket disconnections: %u\n", stats.websocketDisconnections);
#endif
}

/**
 * Record JWT refresh attempt
 */
void recordJWTRefreshAttempt(bool success) {
    if (!statsInitialized) return;
    
    stats.jwtRefreshAttempts++;
    if (success) {
        stats.jwtRefreshSuccesses++;
    }
    
    saveConnectionStats();
    
#ifndef PRODUCTION_BUILD
    Serial.printf("📊 JWT refresh %s: %u/%u (%.1f%%)\n", 
                  success ? "SUCCESS" : "FAILED",
                  stats.jwtRefreshSuccesses, stats.jwtRefreshAttempts,
                  (float)stats.jwtRefreshSuccesses / stats.jwtRefreshAttempts * 100.0);
#endif
}

/**
 * Record system recovery
 */
void recordSystemRecovery() {
    if (!statsInitialized) return;
    
    stats.systemRecoveries++;
    saveConnectionStats();
    
    Serial.printf("🚨 System recovery #%u recorded\n", stats.systemRecoveries);
}

/**
 * Get current connection statistics
 */
ConnectionStats getConnectionStats() {
    return stats;
}

/**
 * Log boot information with reset reason
 */
void logBootInformation() {
    const char* resetReasonStr = getResetReasonString(stats.lastResetReason);
    
    Serial.println("========================================");
    Serial.println("🔄 BOOT INFORMATION");
    Serial.println("========================================");
    Serial.printf("Boot Count: %u\n", stats.totalBootCount);
    Serial.printf("Reset Reason: %s\n", resetReasonStr);
    Serial.printf("WiFi Success Rate: %u/%u (%.1f%%)\n", 
                  stats.wifiConnectSuccesses, stats.wifiConnectAttempts,
                  stats.wifiConnectAttempts > 0 ? 
                  (float)stats.wifiConnectSuccesses / stats.wifiConnectAttempts * 100.0 : 0.0);
    Serial.printf("WebSocket Success Rate: %u/%u (%.1f%%)\n", 
                  stats.websocketConnectSuccesses, stats.websocketConnectAttempts,
                  stats.websocketConnectAttempts > 0 ? 
                  (float)stats.websocketConnectSuccesses / stats.websocketConnectAttempts * 100.0 : 0.0);
    Serial.printf("JWT Refresh Success Rate: %u/%u (%.1f%%)\n", 
                  stats.jwtRefreshSuccesses, stats.jwtRefreshAttempts,
                  stats.jwtRefreshAttempts > 0 ? 
                  (float)stats.jwtRefreshSuccesses / stats.jwtRefreshAttempts * 100.0 : 0.0);
    Serial.printf("Total Recoveries: %u\n", stats.systemRecoveries);
    Serial.printf("WiFi Disconnections: %u\n", stats.wifiDisconnections);
    Serial.printf("WebSocket Disconnections: %u\n", stats.websocketDisconnections);
    Serial.println("========================================");
    
    // Alert on concerning patterns
    if (stats.systemRecoveries > 10) {
        Serial.println("🚨 WARNING: High system recovery count!");
    }
    
    if (stats.totalBootCount > 1 && 
        (stats.lastResetReason == ESP_RST_PANIC || 
         stats.lastResetReason == ESP_RST_TASK_WDT ||
         stats.lastResetReason == ESP_RST_INT_WDT)) {
        Serial.println("🚨 WARNING: Last reset was due to system failure!");
    }
    
    float wifiSuccessRate = stats.wifiConnectAttempts > 0 ? 
                           (float)stats.wifiConnectSuccesses / stats.wifiConnectAttempts : 1.0;
    if (wifiSuccessRate < 0.8 && stats.wifiConnectAttempts > 5) {
        Serial.println("⚠️ WARNING: Low WiFi connection success rate!");
    }
}

/**
 * Print detailed statistics (development only)
 */
void printDetailedConnectionStats() {
#ifndef PRODUCTION_BUILD
    Serial.println("\n📊 DETAILED CONNECTION STATISTICS:");
    Serial.println("==================================");
    
    Serial.printf("System Statistics:\n");
    Serial.printf("  Boot Count: %u\n", stats.totalBootCount);
    Serial.printf("  Last Reset: %s\n", getResetReasonString(stats.lastResetReason));
    Serial.printf("  System Recoveries: %u\n", stats.systemRecoveries);
    
    Serial.printf("\nWiFi Statistics:\n");
    Serial.printf("  Connection Attempts: %u\n", stats.wifiConnectAttempts);
    Serial.printf("  Successful Connections: %u\n", stats.wifiConnectSuccesses);
    Serial.printf("  Disconnections: %u\n", stats.wifiDisconnections);
    Serial.printf("  Success Rate: %.1f%%\n", 
                  stats.wifiConnectAttempts > 0 ? 
                  (float)stats.wifiConnectSuccesses / stats.wifiConnectAttempts * 100.0 : 0.0);
    
    Serial.printf("\nWebSocket Statistics:\n");
    Serial.printf("  Connection Attempts: %u\n", stats.websocketConnectAttempts);
    Serial.printf("  Successful Connections: %u\n", stats.websocketConnectSuccesses);
    Serial.printf("  Disconnections: %u\n", stats.websocketDisconnections);
    Serial.printf("  Success Rate: %.1f%%\n", 
                  stats.websocketConnectAttempts > 0 ? 
                  (float)stats.websocketConnectSuccesses / stats.websocketConnectAttempts * 100.0 : 0.0);
    
    Serial.printf("\nJWT Statistics:\n");
    Serial.printf("  Refresh Attempts: %u\n", stats.jwtRefreshAttempts);
    Serial.printf("  Successful Refreshes: %u\n", stats.jwtRefreshSuccesses);
    Serial.printf("  Success Rate: %.1f%%\n", 
                  stats.jwtRefreshAttempts > 0 ? 
                  (float)stats.jwtRefreshSuccesses / stats.jwtRefreshAttempts * 100.0 : 0.0);
    
    Serial.println("==================================\n");
#endif
}

/**
 * Reset connection statistics (for testing)
 */
void resetConnectionStats() {
    stats = {};
    saveConnectionStats();
    Serial.println("🔄 Connection statistics reset");
}

/**
 * Cleanup connection statistics
 */
void cleanupConnectionStats() {
    if (statsInitialized) {
        saveConnectionStats();
        statsPrefs.end();
        statsInitialized = false;
        Serial.println("🧹 Connection statistics cleanup complete");
    }
}