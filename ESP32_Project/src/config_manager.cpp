#include "config_manager.h"
#include <Preferences.h>
#include <WiFi.h>
#include "config.h"

// Simple configuration check function for main.cpp compatibility
bool isConfigured() {
    // Check if WiFi is configured and we have basic settings
    return WiFi.SSID().length() > 0 && WiFi.psk().length() > 0;
}

static bool configManagerInitialized = false;
static ConfigChangeNotification changeCallbacks[5];
static int changeCallbackCount = 0; 
static bool inSafeMode = false;

Preferences configPrefs;
ConfigManager configManager;

bool ConfigManager::init() {
    Serial.println("🔧 Initializing Configuration Manager...");
    
    if (!configPrefs.begin("teddy-config", false)) {
        Serial.println("❌ Failed to initialize NVS preferences");
        return false;
    }
    
    // Check if this is first boot
    bool isFirstBoot = !configPrefs.getBool("initialized", false);
    
    if (isFirstBoot) {
        Serial.println("🆕 First boot detected - initializing default configuration");
        initializeDefaultConfig();
    }
    
    // Load current configuration
    loadConfiguration();
    
    Serial.println("✅ Configuration Manager initialized");
    return true;
}

void ConfigManager::initializeDefaultConfig() {
    Serial.println("📝 Setting up default configuration...");
    
    // Set default values
    configPrefs.putString("api_token", "");
    configPrefs.putString("device_cert", "");
    configPrefs.putString("private_key", "");
    configPrefs.putString("ca_cert", "");
    configPrefs.putString("wifi_ssid", "");
    configPrefs.putString("wifi_password", "");
    configPrefs.putString("server_host", DEFAULT_SERVER_HOST);
    configPrefs.putInt("server_port", DEFAULT_SERVER_PORT);
    configPrefs.putString("device_id", DEVICE_ID);
    configPrefs.putString("device_secret", DEVICE_SECRET_KEY);
    configPrefs.putString("child_id", "");
    configPrefs.putString("child_name", "");
    configPrefs.putInt("child_age", -1); // -1 تعني غير معرف
    configPrefs.putBool("ssl_enabled", false); // Start with SSL disabled to avoid cert issues
    configPrefs.putBool("ota_enabled", true);
    configPrefs.putBool("configured", false);
    configPrefs.putBool("initialized", true);
    
    Serial.println("✅ Default configuration saved to NVS");
}

void ConfigManager::loadConfiguration() {
    Serial.println("📖 Loading configuration from NVS...");
    
    // Load all configuration values
    config.api_token = configPrefs.getString("api_token", "");
    config.device_cert = configPrefs.getString("device_cert", "");
    config.private_key = configPrefs.getString("private_key", "");
    config.ca_cert = configPrefs.getString("ca_cert", "");
    config.wifi_ssid = configPrefs.getString("wifi_ssid", "");
    config.wifi_password = configPrefs.getString("wifi_password", "");
    config.server_host = configPrefs.getString("server_host", DEFAULT_SERVER_HOST);
    config.server_port = configPrefs.getInt("server_port", DEFAULT_SERVER_PORT);
    config.device_id = configPrefs.getString("device_id", DEVICE_ID);
    config.device_secret = configPrefs.getString("device_secret", DEVICE_SECRET_KEY);
    config.child_id = configPrefs.getString("child_id", "");
    config.child_name = configPrefs.getString("child_name", "");
    config.child_age = configPrefs.getInt("child_age", -1); // -1 تعني غير معرف
    config.ssl_enabled = configPrefs.getBool("ssl_enabled", false);
    config.ota_enabled = configPrefs.getBool("ota_enabled", true);
    config.configured = configPrefs.getBool("configured", false);
    
    printConfiguration();
}

void ConfigManager::saveConfiguration() {
    Serial.println("💾 Saving configuration to NVS...");
    
    configPrefs.putString("api_token", config.api_token);
    configPrefs.putString("device_cert", config.device_cert);
    configPrefs.putString("private_key", config.private_key);
    configPrefs.putString("ca_cert", config.ca_cert);
    configPrefs.putString("wifi_ssid", config.wifi_ssid);
    configPrefs.putString("wifi_password", config.wifi_password);
    configPrefs.putString("server_host", config.server_host);
    configPrefs.putInt("server_port", config.server_port);
    configPrefs.putString("device_id", config.device_id);
    configPrefs.putString("device_secret", config.device_secret);
    configPrefs.putString("child_id", config.child_id);
    configPrefs.putString("child_name", config.child_name);
    configPrefs.putInt("child_age", config.child_age);
    configPrefs.putBool("ssl_enabled", config.ssl_enabled);
    configPrefs.putBool("ota_enabled", config.ota_enabled);
    configPrefs.putBool("configured", config.configured);
    
    Serial.println("✅ Configuration saved successfully");
}

void ConfigManager::printConfiguration() {
    Serial.println("📋 Current Configuration:");
    Serial.println("========================");
    Serial.printf("API Token: %s\n", config.api_token.length() > 0 ? "SET" : "NOT_SET");
    Serial.printf("Device Cert: %s\n", config.device_cert.length() > 0 ? "SET" : "NOT_SET");
    Serial.printf("Private Key: %s\n", config.private_key.length() > 0 ? "SET" : "NOT_SET");
    Serial.printf("CA Cert: %s\n", config.ca_cert.length() > 0 ? "SET" : "NOT_SET");
    Serial.printf("WiFi SSID: %s\n", config.wifi_ssid.length() > 0 ? config.wifi_ssid.c_str() : "NOT_SET");
    Serial.printf("WiFi Password: %s\n", config.wifi_password.length() > 0 ? "SET" : "NOT_SET");
    Serial.printf("Server Host: %s\n", config.server_host.c_str());
    Serial.printf("Server Port: %d\n", config.server_port);
    Serial.printf("Device ID: %s\n", config.device_id.c_str());
    Serial.printf("Device Secret: %s\n", config.device_secret.length() > 0 ? "SET" : "NOT_SET");
    Serial.printf("Child ID: %s\n", config.child_id.length() > 0 ? config.child_id.c_str() : "NOT_SET");
    Serial.printf("Child Name: %s\n", config.child_name.length() > 0 ? config.child_name.c_str() : "NOT_SET");
    if (config.child_age != -1) {
        Serial.printf("Child Age: %d\n", config.child_age);
    }
    Serial.printf("SSL Enabled: %s\n", config.ssl_enabled ? "YES" : "NO");
    Serial.printf("OTA Enabled: %s\n", config.ota_enabled ? "YES" : "NO");
    Serial.printf("Configured: %s\n", config.configured ? "YES" : "NO");
    Serial.println("========================");
}

bool ConfigManager::isWiFiConfigured() {
    return config.wifi_ssid.length() > 0 && config.wifi_password.length() > 0;
}

bool ConfigManager::isDeviceConfigured() {
    return config.configured && 
           config.device_id.length() > 0 && 
           config.server_host.length() > 0;
}

bool ConfigManager::hasSSLCertificates() {
    return config.device_cert.length() > 0 && 
           config.private_key.length() > 0 && 
           config.ca_cert.length() > 0;
}

bool ConfigManager::setWiFiCredentials(const String& ssid, const String& password) {
    config.wifi_ssid = ssid;
    config.wifi_password = password;
    saveConfiguration();
    Serial.printf("✅ WiFi credentials updated: %s\n", ssid.c_str());
    return true;
}

bool ConfigManager::setDeviceInfo(const String& deviceId, const String& deviceSecret) {
    config.device_id = deviceId;
    config.device_secret = deviceSecret;
    saveConfiguration();
    Serial.printf("✅ Device info updated: %s\n", deviceId.c_str());
    return true;
}

bool ConfigManager::setChildInfo(const String& childId, const String& childName, int childAge) {
    if (childId.length() > 0) {
        config.child_id = childId;
    }
    if (childName.length() > 0) {
        config.child_name = childName;
    }
    
    // ✅ إصلاح: قبول أي عمر منطقي
    if (childAge >= 0 && childAge <= 18) {
        config.child_age = childAge;
        Serial.printf("✅ Child age set to: %d\n", childAge);
    } else if (childAge != -1) { // -1 يعني "لا تغيير"
        Serial.printf("⚠️ Invalid age: %d (ignored)\n", childAge);
    }
    
    // فقط إذا كانت كل المعلومات مدخلة
    if (config.child_id.length() > 0 && config.child_name.length() > 0 && config.child_age != -1) {
        config.configured = true;
    }
    
    saveConfiguration();
    Serial.printf("✅ Child info updated: %s (%s, age %d)\n", config.child_name.c_str(), config.child_id.c_str(), config.child_age);
    return true;
}

bool ConfigManager::setSSLCertificates(const String& deviceCert, const String& privateKey, const String& caCert) {
    config.device_cert = deviceCert;
    config.private_key = privateKey;
    config.ca_cert = caCert;
    config.ssl_enabled = true;
    saveConfiguration();
    Serial.println("✅ SSL certificates updated and enabled");
    return true;
}

bool ConfigManager::enableSSL(bool enable) {
    config.ssl_enabled = enable && hasSSLCertificates();
    saveConfiguration();
    Serial.printf("✅ SSL %s\n", config.ssl_enabled ? "enabled" : "disabled");
    return config.ssl_enabled;
}

void ConfigManager::resetConfiguration() {
    Serial.println("🔄 Resetting configuration...");
    configPrefs.clear();
    initializeDefaultConfig();
    loadConfiguration();
    Serial.println("✅ Configuration reset complete");
}

TeddyConfig& ConfigManager::getConfig() {
    return config;
}

// Configuration validation and integrity
ConfigValidationResult ConfigManager::validateConfiguration() {
    ConfigValidationResult result = {};
    result.isValid = true;
    result.errorCount = 0;
    result.warningCount = 0;
    result.validationScore = 1.0;

    Serial.println("🔍 Validating configuration...");

    // Check required fields
    if (config.device_id.length() == 0) {
        result.errors[result.errorCount++] = "device_id is required";
        result.isValid = false;
    }
    
    if (config.server_host.length() == 0) {
        result.errors[result.errorCount++] = "server_host is required";
        result.isValid = false;
    }
    
    if (config.server_port <= 0 || config.server_port > 65535) {
        result.errors[result.errorCount++] = "server_port must be between 1 and 65535";
        result.isValid = false;
    }

    // Validate environment
    if (config.environment != "development" && config.environment != "staging" && 
        config.environment != "production") {
        result.warnings[result.warningCount++] = "Unknown environment: " + config.environment;
        result.validationScore -= 0.1;
    }

    // SSL validation
    if (config.ssl_enabled && !hasSSLCertificates()) {
        result.warnings[result.warningCount++] = "SSL enabled but certificates missing";
        result.validationScore -= 0.2;
    }

    config.validated = result.isValid;
    metadata.isValid = result.isValid;
    metadata.validationErrors = result.errorCount;
    metadata.lastValidation = millis();

    Serial.printf("🔍 Validation result: %s (Score: %.2f)\n", 
                 result.isValid ? "PASSED" : "FAILED", result.validationScore);
    
    return result;
}

void ConfigManager::repairConfiguration() {
    Serial.println("🔧 Repairing configuration...");
    
    // Reset to defaults if critical fields are missing
    if (config.device_id.length() == 0) {
        config.device_id = DEFAULT_DEVICE_ID;
    }
    
    if (config.server_host.length() == 0) {
        config.server_host = DEFAULT_SERVER_HOST;
    }
    
    if (config.server_port <= 0) {
        config.server_port = DEFAULT_SERVER_PORT;
    }
    
    if (config.environment.length() == 0) {
        config.environment = ENVIRONMENT_MODE;
    }
    
    // Save repaired configuration
    saveConfiguration();
    Serial.println("✅ Configuration repaired");
}

void ConfigManager::migrateConfiguration() {
    Serial.println("🔄 Migrating configuration to new version...");
    // Configuration migration logic would go here
    // For now, just update the version
    config.config_version = CONFIG_VERSION_STRING;
    config.firmware_version = FIRMWARE_VERSION;
    saveConfiguration();
    Serial.println("✅ Configuration migration complete");
}

bool ConfigManager::loadFromDynamicConfig() {
    // Integration with DynamicConfig class
    ConfigMetadata dynMetadata = DynamicConfig::getMetadata();
    if (dynMetadata.isValid) {
        config.device_id = getConfigValue("device_id", config.device_id);
        config.server_host = getConfigValue("server_host", config.server_host);
        config.server_port = getConfigValueInt("server_port", config.server_port);
        return true;
    }
    return false;
}

bool ConfigManager::saveToDynamicConfig() {
    // Save current config to dynamic config system
    setConfigValue("device_id", config.device_id);
    setConfigValue("server_host", config.server_host);
    setConfigValue("server_port", config.server_port);
    setConfigValue("environment", config.environment);
    return DynamicConfig::applyConfiguration();
}

void ConfigManager::createConfigurationBackup() {
    backupConfig = config;
    DynamicConfig::createBackup();
    Serial.println("💾 Configuration backup created");
}

bool ConfigManager::restoreConfigurationBackup() {
    if (backupConfig.device_id.length() > 0) {
        config = backupConfig;
        saveConfiguration();
        Serial.println("🔄 Configuration restored from backup");
        return true;
    }
    return false;
}

void ConfigManager::resetToEnvironmentDefaults() {
    Serial.printf("🔄 Resetting to %s environment defaults...\n", ENVIRONMENT_MODE);
    
    // Reset to environment-specific defaults
    config.environment = ENVIRONMENT_MODE;
    config.ssl_enabled = USE_SSL_DEFAULT;
    config.debug_enabled = ENABLE_DEBUG_FEATURES;
    config.log_level = DEFAULT_LOG_LEVEL;
    config.system_check_interval = SYSTEM_CHECK_INTERVAL;
    config.watchdog_timeout = WATCHDOG_TIMEOUT;
    config.server_host = DEFAULT_SERVER_HOST;
    config.server_port = DEFAULT_SERVER_PORT;
    config.websocket_path = DEFAULT_WEBSOCKET_PATH;
    
    saveConfiguration();
    applyEnvironmentDefaults();
}

String ConfigManager::generateConfigurationSummary() {
    String summary = "=== Configuration Summary ===\n";
    summary += "Environment: " + config.environment + "\n";
    summary += "Device ID: " + config.device_id + "\n";
    summary += "Server: " + config.server_host + ":" + String(config.server_port) + "\n";
    summary += "SSL: " + String(config.ssl_enabled ? "Enabled" : "Disabled") + "\n";
    summary += "Configured: " + String(config.configured ? "Yes" : "No") + "\n";
    summary += "Valid: " + String(config.validated ? "Yes" : "No") + "\n";
    return summary;
}

// Global helper functions
bool isConfigManagerInitialized() {
    return configManagerInitialized;
}

void initializeGlobalConfigManager(const String& environment) {
    if (environment.length() > 0) {
        configManager.initWithEnvironment(environment);
    } else {
        configManager.init();
    }
}

void registerConfigChangeNotification(ConfigChangeNotification callback) {
    if (changeCallbackCount < 5) {
        changeCallbacks[changeCallbackCount++] = callback;
    }
}

void unregisterConfigChangeNotification(ConfigChangeNotification callback) {
    for (int i = 0; i < changeCallbackCount; i++) {
        if (changeCallbacks[i] == callback) {
            for (int j = i; j < changeCallbackCount - 1; j++) {
                changeCallbacks[j] = changeCallbacks[j + 1];
            }
            changeCallbackCount--;
            break;
        }
    }
}

String getCurrentConfigurationEnvironment() {
    return configManager.getEnvironment();
}

bool isCurrentConfigurationValid() {
    return configManager.validateConfiguration().isValid;
}

void logCurrentConfigurationStatus() {
    configManager.printDetailedConfiguration();
}

void dumpConfigurationToSerial() {
    Serial.println(configManager.generateConfigurationSummary());
}

void enterConfigurationSafeMode() {
    Serial.println("⚠️ Entering configuration safe mode...");
    inSafeMode = true;
    configManager.resetToEnvironmentDefaults();
}

void exitConfigurationSafeMode() {
    Serial.println("✅ Exiting configuration safe mode...");
    inSafeMode = false;
}

bool isInConfigurationSafeMode() {
    return inSafeMode;
}

// Global instance
ConfigManager& getConfigManager() {
    return configManager;
}