#ifndef CONFIG_MANAGER_H
#define CONFIG_MANAGER_H

#include <Arduino.h>
#include "config.h"

// Simple configuration check function
bool isConfigured();

// Enhanced TeddyConfig with versioning and validation support
struct TeddyConfig {
    // Core identification
    String api_token;
    String device_id;
    String device_secret;
    
    // SSL/TLS certificates
    String device_cert;
    String private_key;
    String ca_cert;
    
    // Network configuration
    String wifi_ssid;
    String wifi_password;
    String server_host;
    int server_port;
    String websocket_path;
    
    // Child information
    String child_id;
    String child_name;
    int child_age = -1; // -1 means not set
    
    // Feature flags
    bool ssl_enabled;
    bool ota_enabled;
    bool debug_enabled;
    bool telemetry_enabled;
    
    // Configuration metadata
    String config_version;
    String environment;
    String firmware_version;
    unsigned long last_updated;
    bool configured;
    bool validated;
    
    // Runtime settings
    int log_level;
    unsigned long system_check_interval;
    unsigned long watchdog_timeout;
};

class ConfigManager {
private:
    TeddyConfig config;
    TeddyConfig backupConfig; // For rollback functionality
    ConfigMetadata metadata;
    
    void initializeDefaultConfig();
    void loadConfiguration();
    void printConfiguration();
    void migrateConfiguration(); // For version migrations
    bool validateConfigurationIntegrity();
    
public:
    // Core initialization and management
    bool init();
    bool initWithEnvironment(const String& environment);
    void saveConfiguration();
    void shutdown();
    
    // Configuration validation and integrity
    ConfigValidationResult validateConfiguration();
    bool verifyConfigurationIntegrity();
    void repairConfiguration();
    
    // Configuration checks
    bool isWiFiConfigured();
    bool isDeviceConfigured();
    bool hasSSLCertificates();
    bool isEnvironmentValid();
    bool isConfigurationExpired();
    
    // Configuration setters with validation
    bool setWiFiCredentials(const String& ssid, const String& password);
    bool setDeviceInfo(const String& deviceId, const String& deviceSecret);
    bool setChildInfo(const String& childId, const String& childName, int childAge);
    bool setSSLCertificates(const String& deviceCert, const String& privateKey, const String& caCert);
    bool setServerConfiguration(const String& host, int port, const String& path = "");
    bool enableSSL(bool enable);
    bool setEnvironment(const String& environment);
    
    // Advanced configuration management
    bool loadFromDynamicConfig();
    bool saveToDynamicConfig();
    void createConfigurationBackup();
    bool restoreConfigurationBackup();
    void resetConfiguration();
    void resetToEnvironmentDefaults();
    
    // Configuration versioning
    String getConfigurationVersion();
    bool upgradeConfiguration(const String& newVersion);
    bool downgradeConfiguration(const String& oldVersion);
    
    // Getters
    TeddyConfig& getConfig();
    ConfigMetadata getMetadata();
    String getEnvironment();
    bool isProductionMode();
    
    // Configuration monitoring
    void startConfigurationMonitoring();
    void stopConfigurationMonitoring();
    void scheduleConfigurationUpdate();
    void handleConfigurationUpdate();
    
    // Utility functions
    void printDetailedConfiguration();
    void exportConfiguration(const String& filename);
    bool importConfiguration(const String& filename);
    String generateConfigurationSummary();
};

// Enhanced global instance accessor with initialization checks
ConfigManager& getConfigManager();
bool isConfigManagerInitialized();
void initializeGlobalConfigManager(const String& environment = "");

// Configuration update notification system
typedef void (*ConfigChangeNotification)(const String& key, const String& oldValue, const String& newValue);
void registerConfigChangeNotification(ConfigChangeNotification callback);
void unregisterConfigChangeNotification(ConfigChangeNotification callback);

// Global configuration helper functions
String getCurrentConfigurationEnvironment();
bool isCurrentConfigurationValid();
void logCurrentConfigurationStatus();
void dumpConfigurationToSerial();

// Configuration emergency functions
void enterConfigurationSafeMode();
void exitConfigurationSafeMode();
bool isInConfigurationSafeMode();

#endif