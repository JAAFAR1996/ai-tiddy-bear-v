#ifndef ENCRYPTION_MANAGER_H
#define ENCRYPTION_MANAGER_H

#include <Arduino.h>

// Encryption manager initialization and cleanup
bool initEncryptionManager();
void cleanupEncryptionManager();

// Data encryption/decryption
String encryptData(const String& plaintext, const String& context = "default");
String decryptData(const String& ciphertext, const String& context = "default");

// Secure storage functions
bool storeSecureData(const String& key, const String& data, const String& context = "default");
String retrieveSecureData(const String& key, const String& context = "default");
bool removeSecureData(const String& key);

// Key management
bool rotateEncryptionKeys();

// Security utilities
void secureMemoryClear(void* ptr, size_t size);

// Internal functions (exposed for testing)
bool initializeMasterKey();
void deriveStorageKey();

#endif