#include "config.h"
#include <Preferences.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <mbedtls/md5.h>
#include <SPIFFS.h>

// Static configuration storage
static Preferences dynamicPrefs;
static DynamicJsonDocument currentConfig(2048);
static DynamicJsonDocument backupConfig(2048);
static ConfigMetadata configMetadata;
static String configFilePath = "/config/teddy_config.json";

// Configuration change callbacks
static ConfigUpdateCallback callbacks[5];
static int callbackCount = 0;

// Initialize SPIFFS if not already initialized
static bool initSPIFFS() {
  if (!SPIFFS.begin(true)) {
    Serial.println("❌ Failed to initialize SPIFFS");
    return false;
  }
  return true;
}

// Configuration access functions
String getConfigValue(const String& key, const String& defaultValue) {
  if (currentConfig.containsKey(key)) {
    return currentConfig[key].as<String>();
  }
  return defaultValue;
}

int getConfigValueInt(const String& key, int defaultValue) {
  if (currentConfig.containsKey(key)) {
    return currentConfig[key].as<int>();
  }
  return defaultValue;
}

bool getConfigValueBool(const String& key, bool defaultValue) {
  if (currentConfig.containsKey(key)) {
    return currentConfig[key].as<bool>();
  }
  return defaultValue;
}

float getConfigValueFloat(const String& key, float defaultValue) {
  if (currentConfig.containsKey(key)) {
    return currentConfig[key].as<float>();
  }
  return defaultValue;
}

bool setConfigValue(const String& key, const String& value) {
  String oldValue = getConfigValue(key, "");
  currentConfig[key] = value;
  
  // Notify callbacks
  for (int i = 0; i < callbackCount; i++) {
    if (callbacks[i] != nullptr) {
      callbacks[i](key, oldValue, value);
    }
  }
  
  return true;
}

bool setConfigValue(const String& key, int value) {
  return setConfigValue(key, String(value));
}

bool setConfigValue(const String& key, bool value) {
  return setConfigValue(key, value ? "true" : "false");
}

bool setConfigValue(const String& key, float value) {
  return setConfigValue(key, String(value, 2));
}

// Configuration callbacks
void registerConfigUpdateCallback(ConfigUpdateCallback callback) {
  if (callbackCount < 5) {
    callbacks[callbackCount++] = callback;
  }
}

void unregisterConfigUpdateCallback(ConfigUpdateCallback callback) {
  for (int i = 0; i < callbackCount; i++) {
    if (callbacks[i] == callback) {
      // Shift remaining callbacks
      for (int j = i; j < callbackCount - 1; j++) {
        callbacks[j] = callbacks[j + 1];
      }
      callbackCount--;
      break;
    }
  }
}

// DynamicConfig class implementation
bool DynamicConfig::loadFromJSON(const String& jsonStr) {
  Serial.println("📥 Loading configuration from JSON...");
  
  DeserializationError error = deserializeJson(currentConfig, jsonStr);
  if (error) {
    Serial.printf("❌ JSON parsing failed: %s\n", error.c_str());
    return false;
  }
  
  // Validate configuration
  ConfigValidationResult result = validate();
  if (!result.isValid) {
    Serial.printf("❌ Configuration validation failed with %d errors\n", result.errorCount);
    for (int i = 0; i < result.errorCount; i++) {
      Serial.printf("  • %s\n", result.errors[i].c_str());
    }
    return false;
  }
  
  // Update metadata
  configMetadata.lastUpdate = millis();
  configMetadata.isValid = true;
  configMetadata.validationErrors = 0;
  configMetadata.checksum = generateConfigChecksum(jsonStr);
  
  Serial.printf("✅ Configuration loaded successfully (Score: %.1f)\n", result.validationScore);
  return true;
}

bool DynamicConfig::loadFromFile(const String& filename) {
  if (!initSPIFFS()) return false;
  
  Serial.printf("📁 Loading configuration from file: %s\n", filename.c_str());
  
  File file = SPIFFS.open(filename, "r");
  if (!file) {
    Serial.printf("❌ Failed to open config file: %s\n", filename.c_str());
    return false;
  }
  
  String jsonStr = file.readString();
  file.close();
  
  return loadFromJSON(jsonStr);
}

bool DynamicConfig::loadFromServer() {
  Serial.println("🌐 Loading configuration from server...");
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi not connected");
    return false;
  }
  
  HTTPClient http;
  http.begin(DEFAULT_CONFIG_UPDATE_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("User-Agent", String("TeddyBear/") + FIRMWARE_VERSION);
  http.addHeader("X-Device-ID", getConfigValue("device_id", DEFAULT_DEVICE_ID));
  http.addHeader("X-Config-Version", configMetadata.version);
  
  int httpResponseCode = http.GET();
  
  if (httpResponseCode == 200) {
    String payload = http.getString();
    http.end();

    // Accept both formats:
    // 1) { "config": { ... } }
    // 2) { ... } plain config (server returns top-level keys)
    DynamicJsonDocument doc(2048);
    DeserializationError error = deserializeJson(doc, payload);
    if (error) {
      Serial.printf("❌ Server response parsing failed: %s\n", error.c_str());
      return false;
    }

    JsonObject cfg = doc.containsKey("config") ? doc["config"].as<JsonObject>()
                                                : doc.as<JsonObject>();

    // Transform keys to device schema expected by validate()/applyConfiguration()
    DynamicJsonDocument transformed(1024);
    transformed["device_id"] = getConfigValue("device_id", DEFAULT_DEVICE_ID);
    if (cfg.containsKey("firmware_version")) {
      transformed["firmware_version"] = cfg["firmware_version"].as<const char*>();
    } else {
      transformed["firmware_version"] = FIRMWARE_VERSION;
    }
    if (cfg.containsKey("environment")) {
      transformed["environment"] = cfg["environment"].as<const char*>();
    } else {
      transformed["environment"] = (cfg.containsKey("tls") && cfg["tls"].as<bool>()) ? "production" : ENVIRONMENT_MODE;
    }
    // Map host/port and websocket path
    if (cfg.containsKey("host")) transformed["server_host"] = cfg["host"].as<const char*>();
    if (cfg.containsKey("port")) transformed["server_port"] = cfg["port"].as<int>();
    if (cfg.containsKey("ws_path")) transformed["websocket_path"] = cfg["ws_path"].as<const char*>();
    if (cfg.containsKey("tls")) transformed["ssl_enabled"] = cfg["tls"].as<bool>();

    String configStr;
    serializeJson(transformed, configStr);
    return loadFromJSON(configStr);
  } else {
    Serial.printf("❌ Server request failed: HTTP %d\n", httpResponseCode);
    http.end();
    return false;
  }
}

String DynamicConfig::saveToJSON() {
  String jsonStr;
  serializeJson(currentConfig, jsonStr);
  return jsonStr;
}

bool DynamicConfig::saveToFile(const String& filename) {
  if (!initSPIFFS()) return false;
  
  Serial.printf("💾 Saving configuration to file: %s\n", filename.c_str());
  
  // Create directory if it doesn't exist
  String dir = filename.substring(0, filename.lastIndexOf('/'));
  if (!SPIFFS.exists(dir)) {
    SPIFFS.mkdir(dir);
  }
  
  File file = SPIFFS.open(filename, "w");
  if (!file) {
    Serial.printf("❌ Failed to create config file: %s\n", filename.c_str());
    return false;
  }
  
  String jsonStr = saveToJSON();
  size_t written = file.print(jsonStr);
  file.close();
  
  if (written == jsonStr.length()) {
    Serial.printf("✅ Configuration saved (%d bytes)\n", written);
    return true;
  } else {
    Serial.printf("❌ Failed to write complete configuration (%d/%d bytes)\n", written, jsonStr.length());
    return false;
  }
}

ConfigValidationResult DynamicConfig::validate() {
  ConfigValidationResult result = {};
  result.isValid = true;
  result.errorCount = 0;
  result.warningCount = 0;
  result.validationScore = 1.0;
  
  Serial.println("🔍 Validating configuration...");
  
  // Check required fields
  String requiredFields[] = {
    "device_id", "firmware_version", "environment", "server_host", "server_port"
  };
  
  for (const String& field : requiredFields) {
    if (!currentConfig.containsKey(field) || currentConfig[field].as<String>().length() == 0) {
      if (result.errorCount < 10) {
        result.errors[result.errorCount] = "Missing required field: " + field;
        result.errorCount++;
      }
      result.isValid = false;
      result.validationScore -= 0.2;
    }
  }
  
  // Validate device_id format (alphanumeric + hyphens, 3-32 chars)
  String deviceId = getConfigValue("device_id", "");
  if (deviceId.length() < 3 || deviceId.length() > 32) {
    if (result.errorCount < 10) {
      result.errors[result.errorCount] = "device_id must be 3-32 characters";
      result.errorCount++;
    }
    result.isValid = false;
    result.validationScore -= 0.1;
  }
  
  // Validate server_port range
  int serverPort = getConfigValueInt("server_port", 0);
  if (serverPort < 1 || serverPort > 65535) {
    if (result.errorCount < 10) {
      result.errors[result.errorCount] = "server_port must be between 1 and 65535";
      result.errorCount++;
    }
    result.isValid = false;
    result.validationScore -= 0.1;
  }
  
  // Validate environment
  String environment = getConfigValue("environment", "");
  if (environment != "development" && environment != "staging" && environment != "production") {
    if (result.warningCount < 5) {
      result.warnings[result.warningCount] = "Unknown environment: " + environment;
      result.warningCount++;
    }
    result.validationScore -= 0.05;
  }
  
  // Check configuration size
  String jsonStr = saveToJSON();
  if (jsonStr.length() > MAX_CONFIG_SIZE) {
    if (result.errorCount < 10) {
      result.errors[result.errorCount] = "Configuration too large: " + String(jsonStr.length()) + " > " + String(MAX_CONFIG_SIZE);
      result.errorCount++;
    }
    result.isValid = false;
    result.validationScore -= 0.1;
  }
  
  // Validate SSL configuration if enabled
  if (getConfigValueBool("ssl_enabled", false)) {
    if (getConfigValue("ca_cert", "").length() == 0 && 
        getConfigValue("device_cert", "").length() == 0) {
      if (result.warningCount < 5) {
        result.warnings[result.warningCount] = "SSL enabled but no certificates configured";
        result.warningCount++;
      }
      result.validationScore -= 0.05;
    }
  }
  
  // Ensure score doesn't go below 0
  result.validationScore = max(0.0f, result.validationScore);
  
  configMetadata.lastValidation = millis();
  configMetadata.validationErrors = result.errorCount;
  configMetadata.isValid = result.isValid;
  
  Serial.printf("🔍 Validation complete: %s (Score: %.2f, Errors: %d, Warnings: %d)\n",
               result.isValid ? "PASSED" : "FAILED", 
               result.validationScore, result.errorCount, result.warningCount);
  
  return result;
}

bool DynamicConfig::applyConfiguration() {
  Serial.println("⚙️ Applying configuration changes...");
  
  // Create backup before applying
  backupConfig = currentConfig;
  
  // Apply environment-specific defaults
  applyEnvironmentDefaults();
  
  // Save to preferences
  if (!dynamicPrefs.begin("dynamic-config", false)) {
    Serial.println("❌ Failed to open preferences");
    return false;
  }
  
  // Save key configuration values
  dynamicPrefs.putString("device_id", getConfigValue("device_id", DEFAULT_DEVICE_ID));
  dynamicPrefs.putString("server_host", getConfigValue("server_host", DEFAULT_SERVER_HOST));
  dynamicPrefs.putInt("server_port", getConfigValueInt("server_port", DEFAULT_SERVER_PORT));
  dynamicPrefs.putString("environment", getConfigValue("environment", ENVIRONMENT_MODE));
  dynamicPrefs.putBool("ssl_enabled", getConfigValueBool("ssl_enabled", USE_SSL_DEFAULT));
  
  // Update runtime configuration
  configMetadata.lastUpdate = millis();
  
  Serial.println("✅ Configuration applied successfully");
  return true;
}

void DynamicConfig::rollbackConfiguration() {
  Serial.println("🔄 Rolling back configuration...");
  currentConfig = backupConfig;
  applyConfiguration();
}

ConfigMetadata DynamicConfig::getMetadata() {
  return configMetadata;
}

String DynamicConfig::getCurrentEnvironment() {
  return getConfigValue("environment", ENVIRONMENT_MODE);
}

bool DynamicConfig::isProductionMode() {
  return DynamicConfig::getCurrentEnvironment() == "production";
}

void DynamicConfig::scheduleConfigUpdate() {
  static unsigned long lastCheck = 0;
  unsigned long now = millis();
  
  if (now - lastCheck > CONFIG_UPDATE_CHECK_INTERVAL) {
    lastCheck = now;
    checkForConfigUpdates();
  }
}

void DynamicConfig::checkForConfigUpdates() {
  Serial.println("🔄 Checking for configuration updates...");
  
  // In a real implementation, this would check a remote server
  // For now, we'll just validate current configuration
  ConfigValidationResult result = validate();
  configMetadata.needsUpdate = !result.isValid || result.validationScore < 0.8;
  
  if (configMetadata.needsUpdate) {
    Serial.println("⚠️ Configuration needs update");
  }
}

void DynamicConfig::createBackup() {
  Serial.println("💾 Creating configuration backup...");
  
  String timestamp = String(millis());
  String backupFile = "/config/backup_" + timestamp + ".json";
  
  if (saveToFile(backupFile)) {
    Serial.printf("✅ Backup created: %s\n", backupFile.c_str());
  }
}

bool DynamicConfig::restoreBackup(int backupIndex) {
  Serial.printf("🔄 Restoring configuration backup #%d...\n", backupIndex);
  
  if (!initSPIFFS()) return false;
  
  // List backup files
  File root = SPIFFS.open("/config");
  if (!root || !root.isDirectory()) {
    Serial.println("❌ No backup directory found");
    return false;
  }
  
  String backupFiles[CONFIG_BACKUP_COUNT];
  int backupCount = 0;
  
  File file = root.openNextFile();
  while (file && backupCount < CONFIG_BACKUP_COUNT) {
    if (String(file.name()).startsWith("backup_")) {
      backupFiles[backupCount++] = file.name();
    }
    file = root.openNextFile();
  }
  root.close();
  
  if (backupIndex >= backupCount) {
    Serial.printf("❌ Backup index %d not found (only %d backups available)\n", backupIndex, backupCount);
    return false;
  }
  
  return loadFromFile("/config/" + backupFiles[backupIndex]);
}

// Environment configuration functions
void loadEnvironmentOverrides() {
  Serial.printf("🌍 Loading environment overrides for: %s\n", ENVIRONMENT_MODE);
  
  // Set environment-specific defaults
  setConfigValue("environment", ENVIRONMENT_MODE);
  setConfigValue("system_check_interval", SYSTEM_CHECK_INTERVAL);
  setConfigValue("log_level", DEFAULT_LOG_LEVEL);
  setConfigValue("debug_enabled", ENABLE_DEBUG_FEATURES);
  setConfigValue("ssl_default", USE_SSL_DEFAULT);
  setConfigValue("watchdog_timeout", WATCHDOG_TIMEOUT);
}

void applyEnvironmentDefaults() {
  Serial.printf("⚙️ Applying environment defaults for: %s\n", DynamicConfig::getCurrentEnvironment().c_str());
  
  String env = DynamicConfig::getCurrentEnvironment();
  
  // Apply environment-specific server configuration
  if (!currentConfig.containsKey("server_host")) {
    setConfigValue("server_host", DEFAULT_SERVER_HOST);
  }
  if (!currentConfig.containsKey("server_port")) {
    setConfigValue("server_port", DEFAULT_SERVER_PORT);
  }
  if (!currentConfig.containsKey("websocket_path")) {
    setConfigValue("websocket_path", DEFAULT_WEBSOCKET_PATH);
  }
  
  // Apply environment-specific features
  if (env == "production") {
    setConfigValue("debug_logging", false);
    setConfigValue("ssl_required", true);
    setConfigValue("telemetry_enabled", true);
  } else if (env == "staging") {
    setConfigValue("debug_logging", true);
    setConfigValue("ssl_required", false);
    setConfigValue("telemetry_enabled", true);
  } else { // development
    setConfigValue("debug_logging", true);
    setConfigValue("ssl_required", false);
    setConfigValue("telemetry_enabled", false);
  }
}

// Utility functions
String generateConfigChecksum(const String& config) {
  mbedtls_md5_context ctx;
  unsigned char hash[16];
  
  mbedtls_md5_init(&ctx);
  mbedtls_md5_starts(&ctx);
  mbedtls_md5_update(&ctx, (const unsigned char*)config.c_str(), config.length());
  mbedtls_md5_finish(&ctx, hash);
  mbedtls_md5_free(&ctx);
  
  String checksum = "";
  for (int i = 0; i < 16; i++) {
    if (hash[i] < 16) checksum += "0";
    checksum += String(hash[i], HEX);
  }
  
  return checksum;
}

bool verifyConfigIntegrity(const String& config, const String& checksum) {
  return generateConfigChecksum(config) == checksum;
}

void logConfigurationState() {
  Serial.println("=== 📋 Configuration State ===");
  Serial.printf("Version: %s\n", configMetadata.version.c_str());
  Serial.printf("Environment: %s\n", configMetadata.environment.c_str());
  Serial.printf("Valid: %s\n", configMetadata.isValid ? "Yes" : "No");
  Serial.printf("Last Update: %lu ms ago\n", millis() - configMetadata.lastUpdate);
  Serial.printf("Last Validation: %lu ms ago\n", millis() - configMetadata.lastValidation);
  Serial.printf("Validation Errors: %d\n", configMetadata.validationErrors);
  Serial.printf("Needs Update: %s\n", configMetadata.needsUpdate ? "Yes" : "No");
  Serial.printf("Checksum: %s\n", configMetadata.checksum.c_str());
  
  // Log current key values
  Serial.println("\n--- Key Configuration Values ---");
  Serial.printf("Device ID: %s\n", getConfigValue("device_id", "NOT_SET").c_str());
  Serial.printf("Server: %s:%d\n", 
                getConfigValue("server_host", "NOT_SET").c_str(),
                getConfigValueInt("server_port", 0));
  Serial.printf("SSL Enabled: %s\n", getConfigValueBool("ssl_enabled", false) ? "Yes" : "No");
  Serial.printf("Environment: %s\n", DynamicConfig::getCurrentEnvironment().c_str());
  Serial.println("==============================");
}

void printEnvironmentInfo() {
  Serial.println("=== 🌍 Environment Information ===");
  Serial.printf("Build Environment: %s\n", BUILD_ENV);
  Serial.printf("Runtime Environment: %s\n", ENVIRONMENT_MODE);
  Serial.printf("Production Mode: %s\n", PRODUCTION_MODE ? "Yes" : "No");
  Serial.printf("SSL Default: %s\n", USE_SSL_DEFAULT ? "Enabled" : "Disabled");
  Serial.printf("Debug Features: %s\n", ENABLE_DEBUG_FEATURES ? "Enabled" : "Disabled");
  Serial.printf("Log Level: %d\n", DEFAULT_LOG_LEVEL);
  Serial.printf("Check Interval: %d ms\n", SYSTEM_CHECK_INTERVAL);
  Serial.printf("Watchdog Timeout: %d ms\n", WATCHDOG_TIMEOUT);
  Serial.println("==================================");
}

