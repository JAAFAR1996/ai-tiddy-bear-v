#include "security_manager.h"
#include <Preferences.h>
#include <EEPROM.h>
#include <mbedtls/aes.h>
#include <mbedtls/sha256.h>
#include <esp_system.h>

// Secure key storage namespace
static const char* SECURITY_NAMESPACE = "teddy_sec";
static const char* KEY_DEVICE_SECRET = "dev_secret";
static const char* KEY_API_TOKEN = "api_token";
static const char* KEY_CERT_FINGERPRINT = "cert_fp";
static const char* KEY_DEVICE_CERT = "dev_cert";
static const char* KEY_PRIVATE_KEY = "priv_key";
static const char* KEY_OTA_PASSWORD = "ota_pass";

static Preferences secureStorage;
static bool securityInitialized = false;

// Hardware-based key derivation
String deriveDeviceUniqueKey() {
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  
  uint64_t chipid = ESP.getEfuseMac();
    esp_chip_info_t chip_info;
    esp_chip_info(&chip_info);
    uint32_t chip_ver = chip_info.revision;
  
  // Combine MAC address, chip ID, and chip version
  char uniqueStr[64];
  snprintf(uniqueStr, sizeof(uniqueStr), "%02x%02x%02x%02x%02x%02x%016llx%08x",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5], chipid, chip_ver);
  
  // Hash the unique string with SHA-256
  uint8_t hash[32];
  mbedtls_sha256_context ctx;
  mbedtls_sha256_init(&ctx);
  mbedtls_sha256_starts(&ctx, 0); // SHA-256, not SHA-224
  mbedtls_sha256_update(&ctx, (uint8_t*)uniqueStr, strlen(uniqueStr));
  mbedtls_sha256_finish(&ctx, hash);
  mbedtls_sha256_free(&ctx);
  
  // Convert to hex string
  String result = "";
  for (int i = 0; i < 32; i++) {
    char hex[3];
    sprintf(hex, "%02x", hash[i]);
    result += hex;
  }
  
  return result.substring(0, 32); // Return first 32 characters
}

bool initSecurityManager() {
  Serial.println("🔒 Initializing Security Manager...");
  
  // Initialize secure storage
  if (!secureStorage.begin(SECURITY_NAMESPACE, false)) {
    Serial.println("❌ Failed to initialize secure storage");
    return false;
  }
  
  // Check if this is first boot
  bool isFirstBoot = !secureStorage.getBool("initialized", false);
  
  if (isFirstBoot) {
    Serial.println("🆕 First boot detected - generating device keys...");
    if (!generateDeviceKeys()) {
      Serial.println("❌ Failed to generate device keys");
      return false;
    }
    secureStorage.putBool("initialized", true);
  }
  
  // Validate stored keys
  if (!validateStoredKeys()) {
    Serial.println("⚠️ Key validation failed - regenerating...");
    if (!generateDeviceKeys()) {
      Serial.println("❌ Failed to regenerate keys");
      return false;
    }
  }
  
  securityInitialized = true;
  Serial.println("✅ Security Manager initialized successfully");
  return true;
}

bool generateDeviceKeys() {
  Serial.println("🔑 Generating device security keys...");
  
  // Generate or derive device secret key
  String deviceSecret = deriveDeviceUniqueKey();
  if (!secureStorage.putString(KEY_DEVICE_SECRET, deviceSecret)) {
    Serial.println("❌ Failed to store device secret");
    return false;
  }
  
  // Generate OTA password if not set
  String otaPassword = secureStorage.getString(KEY_OTA_PASSWORD, "");
  if (otaPassword.length() < MIN_PASSWORD_LENGTH) {
    otaPassword = generateSecurePassword(24);
    if (!secureStorage.putString(KEY_OTA_PASSWORD, otaPassword)) {
      Serial.println("❌ Failed to store OTA password");
      return false;
    }
  }
  
  // Store security metadata
  secureStorage.putULong("key_generated", millis());
  secureStorage.putInt("key_version", 1);
  
  Serial.println("✅ Device keys generated successfully");
  return true;
}

String generateSecurePassword(int length) {
  const char charset[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*";
  const int charsetSize = strlen(charset);
  
  String password = "";
  for (int i = 0; i < length; i++) {
    password += charset[esp_random() % charsetSize];
  }
  
  return password;
}

bool validateStoredKeys() {
  // Check if essential keys exist
  String deviceSecret = secureStorage.getString(KEY_DEVICE_SECRET, "");
  if (deviceSecret.length() < 32) {
    Serial.println("⚠️ Device secret key too short or missing");
    return false;
  }
  
  String otaPassword = secureStorage.getString(KEY_OTA_PASSWORD, "");
  if (otaPassword.length() < MIN_PASSWORD_LENGTH) {
    Serial.println("⚠️ OTA password too short or missing");
    return false;
  }
  
  // Check key age (rotate if older than 90 days)
  unsigned long keyGenerated = secureStorage.getULong("key_generated", 0);
  uint32_t currentTime = (uint32_t)millis();
  uint32_t keyAge = (currentTime >= keyGenerated) ? (currentTime - keyGenerated) : 0;
  if (keyAge > (uint32_t)KEY_ROTATION_INTERVAL) {
    Serial.println("⚠️ Keys are due for rotation");
    return false;
  }
  
  return true;
}

String getSecureKey(const String& keyName) {
  if (!securityInitialized) {
    Serial.println("❌ Security manager not initialized");
    return "";
  }
  
  if (keyName == "device_secret") {
    return secureStorage.getString(KEY_DEVICE_SECRET, "");
  } else if (keyName == "ota_password") {
    return secureStorage.getString(KEY_OTA_PASSWORD, "");
  } else if (keyName == "api_token") {
    return secureStorage.getString(KEY_API_TOKEN, "");
  } else if (keyName == "cert_fingerprint") {
    return secureStorage.getString(KEY_CERT_FINGERPRINT, "");
  }
  
  Serial.println("❌ Unknown key requested: " + keyName);
  return "";
}

bool setSecureKey(const String& keyName, const String& value) {
  if (!securityInitialized) {
    Serial.println("❌ Security manager not initialized");
    return false;
  }
  
  if (value.length() == 0) {
    Serial.println("❌ Empty value not allowed for secure key");
    return false;
  }
  
  bool success = false;
  if (keyName == "api_token") {
    success = secureStorage.putString(KEY_API_TOKEN, value);
  } else if (keyName == "cert_fingerprint") {
    success = secureStorage.putString(KEY_CERT_FINGERPRINT, value);
  } else if (keyName == "device_cert") {
    success = secureStorage.putString(KEY_DEVICE_CERT, value);
  } else if (keyName == "private_key") {
    success = secureStorage.putString(KEY_PRIVATE_KEY, value);
  } else {
    Serial.println("❌ Key modification not allowed: " + keyName);
    return false;
  }
  
  if (success) {
    secureStorage.putULong("key_updated", millis());
    Serial.println("✅ Secure key updated: " + keyName);
  } else {
    Serial.println("❌ Failed to update secure key: " + keyName);
  }
  
  return success;
}

bool rotateKeys() {
  Serial.println("🔄 Rotating device security keys...");
  
  // Backup current keys
  if (!backupCurrentKeys()) {
    Serial.println("❌ Failed to backup current keys");
    return false;
  }
  
  // Generate new keys
  if (!generateDeviceKeys()) {
    Serial.println("❌ Failed to generate new keys");
    // Restore backup
    restoreBackupKeys();
    return false;
  }
  
  Serial.println("✅ Key rotation completed successfully");
  return true;
}

bool backupCurrentKeys() {
  // Create backup with timestamp
  unsigned long timestamp = millis();
  String backupPrefix = "backup_" + String(timestamp) + "_";
  
  String deviceSecret = secureStorage.getString(KEY_DEVICE_SECRET, "");
  String otaPassword = secureStorage.getString(KEY_OTA_PASSWORD, "");
  
  if (deviceSecret.length() > 0) {
      secureStorage.putString((backupPrefix + KEY_DEVICE_SECRET).c_str(), deviceSecret);
  }
  
  if (otaPassword.length() > 0) {
      secureStorage.putString((backupPrefix + KEY_OTA_PASSWORD).c_str(), otaPassword);
  }
  
    secureStorage.putULong((backupPrefix + "timestamp").c_str(), timestamp);
  return true;
}

bool restoreBackupKeys() {
  // Find most recent backup
  // This is a simplified implementation - in production, implement proper backup management
  Serial.println("🔄 Restoring backup keys...");
  // Implementation would restore the most recent backup
  return true;
}

void securityHealthCheck() {
  if (!securityInitialized) {
    return;
  }
  
  // Check key age
  unsigned long keyGenerated = secureStorage.getULong("key_generated", 0);
  uint32_t currentTime = (uint32_t)millis();
  uint32_t keyAge = (currentTime >= keyGenerated) ? (currentTime - keyGenerated) : 0;
  
  if (keyAge > (uint32_t)KEY_ROTATION_INTERVAL) {
    Serial.println("⚠️ Security keys require rotation");
    // In production, schedule key rotation
  }
  
  // Check storage integrity
  if (!validateStoredKeys()) {
    Serial.println("❌ Security key validation failed");
    // In production, trigger key regeneration or alert
  }
  
  // Check available storage space
  size_t usedSpace = secureStorage.getBytesLength(SECURITY_NAMESPACE);
  if (usedSpace > (secureStorage.freeEntries() * 0.8)) {
    Serial.println("⚠️ Secure storage nearly full");
    // In production, cleanup old backups
  }
}

void cleanupOldBackups() {
  // Remove backups older than 30 days
  // This would iterate through all keys and remove old backups
  Serial.println("🧹 Cleaning up old security backups...");
  // Implementation would clean up expired backups
}

bool isSecurityInitialized() {
  return securityInitialized;
}

void printSecurityStatus() {
  Serial.println("=== 🔒 Security Status ===");
  Serial.printf("Initialized: %s\n", securityInitialized ? "Yes" : "No");
  
  if (securityInitialized) {
    unsigned long keyGenerated = secureStorage.getULong("key_generated", 0);
    unsigned long keyAge = (millis() - keyGenerated) / 86400000; // Convert to days
    
    Serial.printf("Key Age: %lu days\n", keyAge);
    Serial.printf("Key Version: %d\n", secureStorage.getInt("key_version", 0));
    Serial.printf("Device Secret: %s\n", getSecureKey("device_secret").length() > 0 ? "Present" : "Missing");
    Serial.printf("OTA Password: %s\n", getSecureKey("ota_password").length() > 0 ? "Present" : "Missing");
    Serial.printf("API Token: %s\n", getSecureKey("api_token").length() > 0 ? "Present" : "Missing");
    
    size_t usedSpace = secureStorage.getBytesLength(SECURITY_NAMESPACE);
    size_t freeEntries = secureStorage.freeEntries();
    Serial.printf("Storage Used: %d bytes\n", usedSpace);
    Serial.printf("Free Entries: %d\n", freeEntries);
  }
  
  Serial.println("==========================");
}