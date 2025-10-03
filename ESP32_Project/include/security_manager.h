#ifndef SECURITY_MANAGER_H
#define SECURITY_MANAGER_H

#include <Arduino.h>

// Security configuration constants
#define MIN_PASSWORD_LENGTH 12
#define MAX_PASSWORD_LENGTH 64
#define KEY_ROTATION_INTERVAL 7776000000UL  // 90 days in milliseconds
#define BACKUP_RETENTION_DAYS 30

// Security Manager API
class SecurityManager {
public:
  // Initialization and cleanup
  static bool init();
  static void cleanup();
  static bool isInitialized();
  
  // Key management
  static String getSecureKey(const String& keyName);
  static bool setSecureKey(const String& keyName, const String& value);
  static bool rotateKeys();
  static bool validateStoredKeys();
  
  // Key generation
  static String generateSecurePassword(int length = 20);
  static String deriveDeviceUniqueKey();
  static bool generateDeviceKeys();
  
  // Backup and recovery
  static bool backupCurrentKeys();
  static bool restoreBackupKeys();
  static void cleanupOldBackups();
  
  // Health and maintenance
  static void securityHealthCheck();
  static void printSecurityStatus();
  
private:
  static bool initialized;
};

// C-style functions for compatibility
bool initSecurityManager();
String getSecureKey(const String& keyName);
bool setSecureKey(const String& keyName, const String& value);
String generateSecurePassword(int length);
String deriveDeviceUniqueKey();
bool generateDeviceKeys();
bool validateStoredKeys();
bool rotateKeys();
bool backupCurrentKeys();
bool restoreBackupKeys();
void securityHealthCheck();
void cleanupOldBackups();
bool isSecurityInitialized();
void printSecurityStatus();

// Key names (use these constants to avoid typos)
#define KEY_NAME_DEVICE_SECRET "device_secret"
#define KEY_NAME_OTA_PASSWORD "ota_password"
#define KEY_NAME_API_TOKEN "api_token"
#define KEY_NAME_CERT_FINGERPRINT "cert_fingerprint"
#define KEY_NAME_DEVICE_CERT "device_cert"
#define KEY_NAME_PRIVATE_KEY "private_key"

// Security validation functions
bool isValidPassword(const String& password);
bool isValidApiToken(const String& token);
bool isValidCertificateFingerprint(const String& fingerprint);

// Encryption utilities (for future use)
String encryptData(const String& data, const String& key);
String decryptData(const String& encryptedData, const String& key);
String hashData(const String& data);

#endif