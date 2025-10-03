#ifndef CONNECTION_STATS_H
#define CONNECTION_STATS_H

#include <Arduino.h>
#include <esp_system.h>

/**
 * Connection Statistics Tracker for Production Monitoring
 * 
 * Tracks and persists:
 * - WiFi connection attempts and success rates
 * - WebSocket connection attempts and success rates  
 * - JWT refresh attempts and success rates
 * - System boot count and reset reasons
 * - System recoveries and disconnections
 * 
 * Data is stored in NVS for persistence across reboots
 */

struct ConnectionStats {
    uint32_t totalBootCount = 0;
    uint32_t wifiConnectAttempts = 0;
    uint32_t wifiConnectSuccesses = 0;
    uint32_t wifiDisconnections = 0;
    uint32_t websocketConnectAttempts = 0;
    uint32_t websocketConnectSuccesses = 0;
    uint32_t websocketDisconnections = 0;
    uint32_t jwtRefreshAttempts = 0;
    uint32_t jwtRefreshSuccesses = 0;
    uint32_t systemRecoveries = 0;
    esp_reset_reason_t lastResetReason = ESP_RST_UNKNOWN;
};

// Initialization and cleanup
bool initConnectionStats();
void cleanupConnectionStats();

// Statistics recording
void recordWiFiAttempt(bool success);
void recordWiFiDisconnection();
void recordWebSocketAttempt(bool success);
void recordWebSocketDisconnection();
void recordJWTRefreshAttempt(bool success);
void recordSystemRecovery();

// Statistics access
ConnectionStats getConnectionStats();
void logBootInformation();
void printDetailedConnectionStats();

// Persistence
void loadConnectionStats();
void saveConnectionStats();
void resetConnectionStats();

#endif // CONNECTION_STATS_H