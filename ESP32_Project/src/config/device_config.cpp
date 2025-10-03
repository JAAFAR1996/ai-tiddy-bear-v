#include "device_config.h"

// Global instance
DeviceConfigManager deviceConfigManager;

// Failover event callback
static FailoverEventCallback failoverCallback = nullptr;

DeviceConfigManager::DeviceConfigManager() {
}

DeviceConfigManager::~DeviceConfigManager() {
  if (initialized) {
    prefs.end();
  }
}

bool DeviceConfigManager::init() {
  Serial.println("🔧 Initializing Device Configuration Manager...");
  
  if (!prefs.begin(CONFIG_NAMESPACE, false)) {
    Serial.println("❌ Failed to initialize preferences");
    return false;
  }
  
  initialized = true;
  
  // Load existing configuration
  if (!loadConfig()) {
    Serial.println("⚠️  Using default configuration");
    // Save defaults to flash
    saveConfig();
  }
  
  Serial.printf("✅ Config Manager initialized - Primary: %s:%d\n", 
                config.primaryHost, config.tlsPort);
  
  if (config.hasSecondaryHost) {
    Serial.printf("🔄 Failover enabled - Secondary: %s:%d\n", 
                  config.secondaryHost, config.tlsPort);
  } else {
    Serial.println("⚠️  No secondary host configured - failover disabled");
  }
  
  return true;
}

bool DeviceConfigManager::loadConfig() {
  if (!initialized) {
    Serial.println("❌ Config manager not initialized");
    return false;
  }
  
  Serial.println("📖 Loading device configuration from flash...");
  
  // Load primary host
  String primaryHost = prefs.getString(KEY_PRIMARY_HOST, DEFAULT_PRIMARY_HOST);
  strncpy(config.primaryHost, primaryHost.c_str(), MAX_HOST_LENGTH - 1);
  config.primaryHost[MAX_HOST_LENGTH - 1] = '\0';
  
  // Load secondary host
  String secondaryHost = prefs.getString(KEY_SECONDARY_HOST, DEFAULT_SECONDARY_HOST);
  strncpy(config.secondaryHost, secondaryHost.c_str(), MAX_HOST_LENGTH - 1);
  config.secondaryHost[MAX_HOST_LENGTH - 1] = '\0';
  config.hasSecondaryHost = (strlen(config.secondaryHost) > 0);
  
  // Load TLS port
  config.tlsPort = prefs.getUShort(KEY_TLS_PORT, DEFAULT_TLS_PORT);
  
  // Load failover state
  config.failover.currentHostIndex = prefs.getUChar(KEY_CURRENT_HOST_INDEX, 0);
  config.failover.consecutiveFailures = prefs.getUChar(KEY_FAILOVER_COUNT, 0);
  
  Serial.printf("📋 Loaded - Primary: %s, Secondary: %s, Port: %d\n", 
                config.primaryHost, 
                config.hasSecondaryHost ? config.secondaryHost : "none", 
                config.tlsPort);
  
  return true;
}

bool DeviceConfigManager::saveConfig() {
  if (!initialized) {
    Serial.println("❌ Config manager not initialized");
    return false;
  }
  
  Serial.println("💾 Saving device configuration to flash...");
  
  prefs.putString(KEY_PRIMARY_HOST, config.primaryHost);
  prefs.putString(KEY_SECONDARY_HOST, config.secondaryHost);
  prefs.putUShort(KEY_TLS_PORT, config.tlsPort);
  prefs.putUChar(KEY_CURRENT_HOST_INDEX, config.failover.currentHostIndex);
  prefs.putUChar(KEY_FAILOVER_COUNT, config.failover.consecutiveFailures);
  
  Serial.println("✅ Configuration saved successfully");
  return true;
}

DeviceServerConfig& DeviceConfigManager::getConfig() {
  return config;
}

bool DeviceConfigManager::setPrimaryHost(const char* host) {
  if (!validateHost(host)) {
    Serial.printf("❌ Invalid primary host: %s\n", host);
    return false;
  }
  
  strncpy(config.primaryHost, host, MAX_HOST_LENGTH - 1);
  config.primaryHost[MAX_HOST_LENGTH - 1] = '\0';
  
  Serial.printf("✅ Primary host set to: %s\n", config.primaryHost);
  saveConfig();
  return true;
}

bool DeviceConfigManager::setSecondaryHost(const char* host) {
  if (strlen(host) == 0) {
    // Disable secondary host
    strcpy(config.secondaryHost, "");
    config.hasSecondaryHost = false;
    Serial.println("✅ Secondary host disabled");
  } else {
    if (!validateHost(host)) {
      Serial.printf("❌ Invalid secondary host: %s\n", host);
      return false;
    }
    
    strncpy(config.secondaryHost, host, MAX_HOST_LENGTH - 1);
    config.secondaryHost[MAX_HOST_LENGTH - 1] = '\0';
    config.hasSecondaryHost = true;
    Serial.printf("✅ Secondary host set to: %s\n", config.secondaryHost);
  }
  
  saveConfig();
  return true;
}

bool DeviceConfigManager::setTlsPort(uint16_t port) {
  // ✅ Fixed type-limits warning: uint16_t cannot exceed 65535
  if (port == 0) {
    Serial.printf("❌ Invalid TLS port: %d (port 0 not allowed)\n", port);
    return false;
  }
  
  // Optional: Block privileged ports in production
  #ifdef PRODUCTION_BUILD
  if (port < 1024) {
    Serial.printf("⚠️  [PROD] Using privileged port: %d\n", port);
  }
  #endif
  
  config.tlsPort = port;
  Serial.printf("✅ TLS port set to: %d\n", config.tlsPort);
  saveConfig();
  return true;
}

const char* DeviceConfigManager::getCurrentHost() {
  if (config.failover.currentHostIndex == 1 && config.hasSecondaryHost) {
    return config.secondaryHost;
  }
  return config.primaryHost;
}

uint16_t DeviceConfigManager::getCurrentPort() {
  return config.tlsPort;
}

bool DeviceConfigManager::reportConnectionFailure(const char* host) {
  config.totalFailures++;
  config.failover.consecutiveFailures++;
  config.failover.lastFailureTime = millis();
  
  updateFailoverBackoff();
  
  Serial.printf("❌ Connection failure to %s (consecutive: %d)\n", 
                host, config.failover.consecutiveFailures);
  
  logFailoverEvent("failure", host);
  
  // Check if we should failover after 3 consecutive failures
  if (config.failover.consecutiveFailures >= MAX_FAILOVER_ATTEMPTS) {
    if (config.failover.currentHostIndex == 0 && config.hasSecondaryHost) {
      Serial.println("🔄 Maximum failures reached - attempting failover...");
      return performFailover();
    } else if (config.failover.currentHostIndex == 1) {
      Serial.println("⚠️  Both hosts failing - resetting to primary");
      resetToPrimary();
    }
  }
  
  saveConfig();
  return false;
}

void DeviceConfigManager::reportConnectionSuccess(const char* host) {
  config.lastSuccessTime = millis();
  
  if (config.failover.currentHostIndex == 0) {
    config.primarySuccessCount++;
  } else {
    config.secondarySuccessCount++;
  }
  
  // Reset failure counters on success
  config.failover.consecutiveFailures = 0;
  config.failover.currentBackoffLevel = 0;
  config.failover.isInFailoverMode = false;
  
  Serial.printf("✅ Connection success to %s\n", host);
  logFailoverEvent("success", host);
  
  saveConfig();
}

bool DeviceConfigManager::shouldFailover() {
  return config.failover.consecutiveFailures >= MAX_FAILOVER_ATTEMPTS && 
         config.hasSecondaryHost && 
         config.failover.currentHostIndex == 0;
}

bool DeviceConfigManager::performFailover() {
  if (!config.hasSecondaryHost) {
    Serial.println("❌ Failover requested but no secondary host configured");
    return false;
  }
  
  if (config.failover.currentHostIndex == 1) {
    Serial.println("❌ Already using secondary host");
    return false;
  }
  
  Serial.printf("🔄 FAILOVER: Switching from %s to %s\n", 
                config.primaryHost, config.secondaryHost);
  
  config.failover.currentHostIndex = 1;
  config.failover.consecutiveFailures = 0;
  config.failover.currentBackoffLevel = 0;
  config.failover.isInFailoverMode = true;
  config.failover.failoverStartTime = millis();
  
  logFailoverEvent("failover", config.primaryHost);
  
  if (failoverCallback) {
    failoverCallback("failover", config.primaryHost, config.secondaryHost);
  }
  
  saveConfig();
  return true;
}

void DeviceConfigManager::resetToPrimary() {
  if (config.failover.currentHostIndex == 0) {
    return; // Already using primary
  }
  
  Serial.printf("🔄 RESET: Switching back to primary host %s\n", config.primaryHost);
  
  config.failover.currentHostIndex = 0;
  config.failover.consecutiveFailures = 0;
  config.failover.currentBackoffLevel = 0;
  config.failover.isInFailoverMode = false;
  
  logFailoverEvent("reset_to_primary", config.secondaryHost);
  
  if (failoverCallback) {
    failoverCallback("reset_to_primary", config.secondaryHost, config.primaryHost);
  }
  
  saveConfig();
}

bool DeviceConfigManager::isUsingSecondary() {
  return config.failover.currentHostIndex == 1 && config.hasSecondaryHost;
}

bool DeviceConfigManager::isReadyForRetry() {
  if (config.failover.lastFailureTime == 0) {
    return true; // No previous failures
  }
  
  unsigned long elapsed = millis() - config.failover.lastFailureTime;
  unsigned long requiredDelay = config.failover.backoffDelays[config.failover.currentBackoffLevel];
  
  return elapsed >= requiredDelay;
}

unsigned long DeviceConfigManager::getNextRetryDelay() {
  return config.failover.backoffDelays[config.failover.currentBackoffLevel];
}

void DeviceConfigManager::printStatus() {
  Serial.println("=== 🔧 Device Server Configuration ===");
  Serial.printf("Primary Host: %s:%d\n", config.primaryHost, config.tlsPort);
  Serial.printf("Secondary Host: %s\n", 
                config.hasSecondaryHost ? config.secondaryHost : "Not configured");
  Serial.printf("Current Active: %s (%s)\n", 
                getCurrentHost(), 
                isUsingSecondary() ? "Secondary" : "Primary");
  Serial.printf("Consecutive Failures: %d/%d\n", 
                config.failover.consecutiveFailures, MAX_FAILOVER_ATTEMPTS);
  Serial.printf("Backoff Level: %d (Delay: %lu ms)\n", 
                config.failover.currentBackoffLevel,
                getNextRetryDelay());
  Serial.printf("Connection Stats: Primary=%lu, Secondary=%lu, Failures=%lu\n",
                config.primarySuccessCount, config.secondarySuccessCount, config.totalFailures);
  Serial.printf("Last Success: %lu ms ago\n", 
                config.lastSuccessTime > 0 ? millis() - config.lastSuccessTime : 0);
  Serial.printf("Failover Mode: %s\n", 
                config.failover.isInFailoverMode ? "Active" : "Inactive");
  Serial.println("=====================================");
}

void DeviceConfigManager::resetFailoverState() {
  Serial.println("🔄 Resetting failover state...");
  
  config.failover.consecutiveFailures = 0;
  config.failover.currentBackoffLevel = 0;
  config.failover.lastFailureTime = 0;
  config.failover.currentHostIndex = 0;
  config.failover.isInFailoverMode = false;
  config.failover.failoverStartTime = 0;
  
  saveConfig();
  
  Serial.println("✅ Failover state reset to defaults");
}

void DeviceConfigManager::getConnectionStats(unsigned long& primarySuccess, 
                                            unsigned long& secondarySuccess, 
                                            unsigned long& totalFailures) {
  primarySuccess = config.primarySuccessCount;
  secondarySuccess = config.secondarySuccessCount;
  totalFailures = config.totalFailures;
}

void DeviceConfigManager::updateFailoverBackoff() {
  if (config.failover.currentBackoffLevel < 7) { // Max index in backoffDelays array
    config.failover.currentBackoffLevel++;
  }
}

bool DeviceConfigManager::validateHost(const char* host) {
  if (!host || strlen(host) == 0 || strlen(host) >= MAX_HOST_LENGTH) {
    return false;
  }
  
  // Basic hostname validation (no spaces, valid characters)
  for (int i = 0; host[i] != '\0'; i++) {
    char c = host[i];
    if (!(isalnum(c) || c == '.' || c == '-' || c == '_')) {
      return false;
    }
  }
  
  return true;
}

void DeviceConfigManager::logFailoverEvent(const char* event, const char* host) {
  Serial.printf("📊 Failover Event: %s", event);
  if (host) {
    Serial.printf(" (host: %s)", host);
  }
  Serial.printf(" - Consecutive failures: %d, Backoff level: %d\n",
                config.failover.consecutiveFailures, config.failover.currentBackoffLevel);
}

// Convenience functions
const char* getActiveServerHost() {
  return deviceConfigManager.getCurrentHost();
}

uint16_t getActiveServerPort() {
  return deviceConfigManager.getCurrentPort();
}

bool reportServerFailure(const char* host) {
  return deviceConfigManager.reportConnectionFailure(host);
}

void reportServerSuccess(const char* host) {
  deviceConfigManager.reportConnectionSuccess(host);
}

bool isServerFailoverActive() {
  return deviceConfigManager.isUsingSecondary();
}

void printServerStatus() {
  deviceConfigManager.printStatus();
}

void setFailoverEventCallback(FailoverEventCallback callback) {
  failoverCallback = callback;
}