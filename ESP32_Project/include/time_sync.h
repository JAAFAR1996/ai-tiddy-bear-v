#ifndef TIME_SYNC_H
#define TIME_SYNC_H

#include <time.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Setup production-ready NTP time synchronization
 * Configures multiple NTP servers with fallback handling
 */
void setupProductionTimeSync();

/**
 * Get current timestamp as Unix epoch
 * Returns time in seconds since 1970-01-01 00:00:00 UTC
 */
time_t getCurrentTimestamp();

/**
 * Check if time is synchronized
 * Returns true if time has been successfully synchronized with NTP
 */
bool isTimeSynced();

/**
 * Force sync time with NTP servers
 * Returns true if sync was successful, false otherwise
 */
bool syncTimeWithNTP();

// Non-blocking request to (re)start SNTP sync
void requestSntpSync();

/**
 * Production-ready time sync strategy with multiple fallbacks
 * Returns true if any time source was successful
 */
bool productionTimeSync();

#ifdef __cplusplus
}
#endif

#endif // TIME_SYNC_H
