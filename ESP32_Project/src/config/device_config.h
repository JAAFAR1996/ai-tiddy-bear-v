#pragma once

#include <Arduino.h>
#include <Preferences.h>

// Device configuration keys for EEPROM/Flash storage
#define CONFIG_NAMESPACE "teddy-server"
#define KEY_PRIMARY_HOST "primary_host"
#define KEY_SECONDARY_HOST "secondary_host"
#define KEY_TLS_PORT "tls_port"
#define KEY_FAILOVER_COUNT "failover_count"
#define KEY_CURRENT_HOST_INDEX "current_host"
#define KEY_LAST_SUCCESSFUL_HOST "last_success"

// Default configuration values
#ifdef PRODUCTION_BUILD
  #define DEFAULT_PRIMARY_HOST "192.168.0.37"
  #define DEFAULT_TLS_PORT 80
#else
  // Development defaults: local server
  #define DEFAULT_PRIMARY_HOST "127.0.0.1"
  #define DEFAULT_TLS_PORT 8000
#endif
#define DEFAULT_SECONDARY_HOST ""  // Empty - can be configured later
#define MAX_HOST_LENGTH 128
#define MAX_FAILOVER_ATTEMPTS 3
#define MAX_BACKOFF_DELAY_MS 30000  // 30 seconds maximum

// Failover and retry configuration
struct FailoverConfig {
  unsigned long backoffDelays[8] = {1000, 2000, 4000, 8000, 16000, 30000, 30000, 30000}; // Exponential with 30s cap
  int currentBackoffLevel = 0;
  unsigned long lastFailureTime = 0;
  int consecutiveFailures = 0;
  int currentHostIndex = 0;  // 0 = primary, 1 = secondary
  bool isInFailoverMode = false;
  unsigned long failoverStartTime = 0;
};

// Device server configuration
struct DeviceServerConfig {
  char primaryHost[MAX_HOST_LENGTH];
  char secondaryHost[MAX_HOST_LENGTH];
  uint16_t tlsPort;
  bool hasSecondaryHost;
  
  // Runtime failover state
  FailoverConfig failover;
  
  // Statistics
  unsigned long primarySuccessCount = 0;
  unsigned long secondarySuccessCount = 0;
  unsigned long totalFailures = 0;
  unsigned long lastSuccessTime = 0;
  
  DeviceServerConfig() {
    strncpy(primaryHost, DEFAULT_PRIMARY_HOST, MAX_HOST_LENGTH - 1);
    primaryHost[MAX_HOST_LENGTH - 1] = '\0';
    
    strcpy(secondaryHost, DEFAULT_SECONDARY_HOST);
    tlsPort = DEFAULT_TLS_PORT;
    hasSecondaryHost = (strlen(secondaryHost) > 0);
  }
};

class DeviceConfigManager {
private:
  Preferences prefs;
  DeviceServerConfig config;
  bool initialized = false;

public:
  DeviceConfigManager();
  ~DeviceConfigManager();
  
  /**
   * @brief Initialize device configuration manager
   * @return true if initialization successful
   */
  bool init();
  
  /**
   * @brief Load configuration from flash storage
   * @return true if configuration loaded successfully
   */
  bool loadConfig();
  
  /**
   * @brief Save current configuration to flash storage
   * @return true if configuration saved successfully
   */
  bool saveConfig();
  
  /**
   * @brief Get current server configuration
   * @return Reference to server configuration
   */
  DeviceServerConfig& getConfig();
  
  /**
   * @brief Set primary host
   * @param host Primary server hostname
   * @return true if set successfully
   */
  bool setPrimaryHost(const char* host);
  
  /**
   * @brief Set secondary host for failover
   * @param host Secondary server hostname (empty string to disable)
   * @return true if set successfully
   */
  bool setSecondaryHost(const char* host);
  
  /**
   * @brief Set TLS port
   * @param port TLS port number
   * @return true if set successfully
   */
  bool setTlsPort(uint16_t port);
  
  /**
   * @brief Get current active host (considering failover)
   * @return Current active hostname
   */
  const char* getCurrentHost();
  
  /**
   * @brief Get current active port
   * @return Current TLS port
   */
  uint16_t getCurrentPort();
  
  /**
   * @brief Report connection failure for failover logic
   * @param host Hostname that failed
   * @return true if should try failover
   */
  bool reportConnectionFailure(const char* host);
  
  /**
   * @brief Report connection success
   * @param host Hostname that succeeded
   */
  void reportConnectionSuccess(const char* host);
  
  /**
   * @brief Check if should attempt failover
   * @return true if failover should be attempted
   */
  bool shouldFailover();
  
  /**
   * @brief Perform failover to secondary host
   * @return true if failover available and performed
   */
  bool performFailover();
  
  /**
   * @brief Reset to primary host
   */
  void resetToPrimary();
  
  /**
   * @brief Check if currently using secondary host
   * @return true if using secondary host
   */
  bool isUsingSecondary();
  
  /**
   * @brief Check if sufficient time has passed for retry
   * @return true if ready to retry connection
   */
  bool isReadyForRetry();
  
  /**
   * @brief Get next retry delay in milliseconds
   * @return Delay before next retry attempt
   */
  unsigned long getNextRetryDelay();
  
  /**
   * @brief Print current configuration and status
   */
  void printStatus();
  
  /**
   * @brief Reset failover statistics and state
   */
  void resetFailoverState();
  
  /**
   * @brief Get connection statistics
   * @param primarySuccess Output parameter for primary success count
   * @param secondarySuccess Output parameter for secondary success count
   * @param totalFailures Output parameter for total failure count
   */
  void getConnectionStats(unsigned long& primarySuccess, unsigned long& secondarySuccess, unsigned long& totalFailures);

private:
  void updateFailoverBackoff();
  bool validateHost(const char* host);
  void logFailoverEvent(const char* event, const char* host = nullptr);
};

// Global device configuration instance
extern DeviceConfigManager deviceConfigManager;

// Convenience functions
const char* getActiveServerHost();
uint16_t getActiveServerPort();
bool reportServerFailure(const char* host);
void reportServerSuccess(const char* host);
bool isServerFailoverActive();
void printServerStatus();

// Failover event callbacks
typedef void (*FailoverEventCallback)(const char* event, const char* fromHost, const char* toHost);
void setFailoverEventCallback(FailoverEventCallback callback);
