#include "security_manager.h"
#ifdef __cplusplus
extern "C" {
#endif
#include <mbedtls/aes.h>
#include <mbedtls/gcm.h>
#include <mbedtls/entropy.h>
#include <mbedtls/ctr_drbg.h>
#include <mbedtls/base64.h>  // mbedTLS base64 for secure encryption operations
#include <mbedtls/md.h>
#ifdef __cplusplus
}
#endif
#include <Preferences.h>

// Forward declarations for used functions
// mbedtls types forward declarations
#include <mbedtls/md.h>
bool initializeMasterKey();
void deriveStorageKey();

// Enhanced encryption system for stored data
static Preferences securePrefs;
static mbedtls_entropy_context entropy;
static mbedtls_ctr_drbg_context ctr_drbg;
static bool encryptionInitialized = false;

// Encryption configuration
#define ENCRYPTION_KEY_SIZE 32  // 256-bit AES
#define AES_IV_SIZE 16
#define AES_TAG_SIZE 16
#define MAX_ENCRYPTED_SIZE 2048

// Secure storage keys
static uint8_t masterKey[ENCRYPTION_KEY_SIZE];
static uint8_t storageKey[ENCRYPTION_KEY_SIZE];

bool initEncryptionManager() {
  Serial.println("🔒 Initializing Encryption Manager...");
  
  // Initialize entropy and random number generator
  mbedtls_entropy_init(&entropy);
  mbedtls_ctr_drbg_init(&ctr_drbg);
  
  const char* pers = "ai_teddy_encryption";
  int ret = mbedtls_ctr_drbg_seed(&ctr_drbg, mbedtls_entropy_func, &entropy,
                                  (const unsigned char*)pers, strlen(pers));
  
  if (ret != 0) {
    Serial.printf("❌ Failed to seed RNG: -0x%04x\n", -ret);
    return false;
  }
  
  // Initialize secure preferences
  if (!securePrefs.begin("secure_data", false)) {
    Serial.println("❌ Failed to initialize secure preferences");
    return false;
  }
  
  // Generate or retrieve master key
  if (!initializeMasterKey()) {
    Serial.println("❌ Failed to initialize master key");
    return false;
  }
  
  // Derive storage key from master key
  deriveStorageKey();
  
  encryptionInitialized = true;
  Serial.println("✅ Encryption Manager initialized");
  return true;
}

bool initializeMasterKey() {
  // Try to load existing master key
  size_t keySize = securePrefs.getBytesLength("master_key");
  
  if (keySize == ENCRYPTION_KEY_SIZE) {
    size_t retrieved = securePrefs.getBytes("master_key", masterKey, ENCRYPTION_KEY_SIZE);
    if (retrieved == ENCRYPTION_KEY_SIZE) {
      Serial.println("🔑 Master key loaded from secure storage");
      return true;
    }
  }
  
  // Generate new master key
  Serial.println("🔑 Generating new master key...");
  
  int ret = mbedtls_ctr_drbg_random(&ctr_drbg, masterKey, ENCRYPTION_KEY_SIZE);
  if (ret != 0) {
    Serial.printf("❌ Failed to generate master key: -0x%04x\n", -ret);
    return false;
  }
  
  // Store master key securely
  size_t stored = securePrefs.putBytes("master_key", masterKey, ENCRYPTION_KEY_SIZE);
  if (stored != ENCRYPTION_KEY_SIZE) {
    Serial.println("❌ Failed to store master key");
    return false;
  }
  
  Serial.println("✅ Master key generated and stored");
  return true;
}

void deriveStorageKey() {
  // Use HKDF-like derivation: HMAC-SHA256(master_key, "storage_key_salt")
  const char* salt = "storage_key_salt_ai_teddy_bear_v1";
  
  mbedtls_md_context_t md_ctx;
  const mbedtls_md_info_t* md_info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  
  mbedtls_md_init(&md_ctx);
  mbedtls_md_setup(&md_ctx, md_info, 1);  // 1 = HMAC
  
  mbedtls_md_hmac_starts(&md_ctx, masterKey, ENCRYPTION_KEY_SIZE);
  mbedtls_md_hmac_update(&md_ctx, (const unsigned char*)salt, strlen(salt));
  mbedtls_md_hmac_finish(&md_ctx, storageKey);
  
  mbedtls_md_free(&md_ctx);
  
  Serial.println("🔑 Storage key derived from master key");
}

// Encrypt data for secure storage
String encryptData(const String& plaintext, const String& context) {
  if (!encryptionInitialized || plaintext.length() == 0) {
    return "";
  }
  
  // Generate random IV
  uint8_t iv[AES_IV_SIZE];
  int ret = mbedtls_ctr_drbg_random(&ctr_drbg, iv, AES_IV_SIZE);
  if (ret != 0) {
    Serial.println("❌ Failed to generate IV");
    return "";
  }
  
  // Prepare buffers
  size_t inputLen = plaintext.length();
  uint8_t* input = (uint8_t*)plaintext.c_str();
  uint8_t output[MAX_ENCRYPTED_SIZE];
  uint8_t tag[AES_TAG_SIZE];
  
  if (inputLen > MAX_ENCRYPTED_SIZE - AES_TAG_SIZE - AES_IV_SIZE) {
    Serial.println("❌ Data too large for encryption");
    return "";
  }
  
  // Initialize GCM context
  mbedtls_gcm_context gcm;
  mbedtls_gcm_init(&gcm);
  
  ret = mbedtls_gcm_setkey(&gcm, MBEDTLS_CIPHER_ID_AES, storageKey, 256);
  if (ret != 0) {
    Serial.printf("❌ Failed to set encryption key: -0x%04x\n", -ret);
    mbedtls_gcm_free(&gcm);
    return "";
  }
  
  // Add context as additional authenticated data
  const char* aadData = context.c_str();
  size_t aadLen = context.length();
  
  // Encrypt
  ret = mbedtls_gcm_crypt_and_tag(&gcm, MBEDTLS_GCM_ENCRYPT, inputLen,
                                  iv, AES_IV_SIZE,
                                  (const unsigned char*)aadData, aadLen,
                                  input, output,
                                  AES_TAG_SIZE, tag);
  
  mbedtls_gcm_free(&gcm);
  
  if (ret != 0) {
    Serial.printf("❌ Encryption failed: -0x%04x\n", -ret);
    return "";
  }
  
  // Combine IV + encrypted data + tag
  uint8_t combined[AES_IV_SIZE + MAX_ENCRYPTED_SIZE + AES_TAG_SIZE];
  memcpy(combined, iv, AES_IV_SIZE);
  memcpy(combined + AES_IV_SIZE, output, inputLen);
  memcpy(combined + AES_IV_SIZE + inputLen, tag, AES_TAG_SIZE);
  
  // Base64 encode
  size_t totalLen = AES_IV_SIZE + inputLen + AES_TAG_SIZE;
  size_t base64Len;
  mbedtls_base64_encode(nullptr, 0, &base64Len, combined, totalLen);
  
  char* base64Output = (char*)malloc(base64Len + 1);
  if (!base64Output) {
    Serial.println("❌ Failed to allocate base64 buffer");
    return "";
  }
  
  ret = mbedtls_base64_encode((unsigned char*)base64Output, base64Len + 1, 
                             &base64Len, combined, totalLen);
  
  if (ret != 0) {
    Serial.printf("❌ Base64 encoding failed: -0x%04x\n", -ret);
    free(base64Output);
    return "";
  }
  
  base64Output[base64Len] = '\0';
  String result = String(base64Output);
  free(base64Output);
  
  Serial.printf("🔒 Data encrypted (%d -> %d bytes)\n", inputLen, result.length());
  return result;
}

// Decrypt data from secure storage
String decryptData(const String& ciphertext, const String& context) {
  if (!encryptionInitialized || ciphertext.length() == 0) {
    return "";
  }
  
  // Base64 decode
  size_t decodedLen;
  int ret = mbedtls_base64_decode(nullptr, 0, &decodedLen, 
                                 (const unsigned char*)ciphertext.c_str(), 
                                 ciphertext.length());
  
  if (ret != MBEDTLS_ERR_BASE64_BUFFER_TOO_SMALL) {
    Serial.println("❌ Base64 decode size calculation failed");
    return "";
  }
  
  uint8_t* decoded = (uint8_t*)malloc(decodedLen);
  if (!decoded) {
    Serial.println("❌ Failed to allocate decode buffer");
    return "";
  }
  
  ret = mbedtls_base64_decode(decoded, decodedLen, &decodedLen,
                             (const unsigned char*)ciphertext.c_str(),
                             ciphertext.length());
  
  if (ret != 0) {
    Serial.printf("❌ Base64 decode failed: -0x%04x\n", -ret);
    free(decoded);
    return "";
  }
  
  // Extract IV, ciphertext, and tag
  if (decodedLen < AES_IV_SIZE + AES_TAG_SIZE) {
    Serial.println("❌ Decoded data too small");
    free(decoded);
    return "";
  }
  
  uint8_t* iv = decoded;
  uint8_t* encryptedData = decoded + AES_IV_SIZE;
  size_t encryptedLen = decodedLen - AES_IV_SIZE - AES_TAG_SIZE;
  uint8_t* tag = decoded + AES_IV_SIZE + encryptedLen;
  
  // Decrypt
  uint8_t output[MAX_ENCRYPTED_SIZE];
  
  mbedtls_gcm_context gcm;
  mbedtls_gcm_init(&gcm);
  
  ret = mbedtls_gcm_setkey(&gcm, MBEDTLS_CIPHER_ID_AES, storageKey, 256);
  if (ret != 0) {
    Serial.printf("❌ Failed to set decryption key: -0x%04x\n", -ret);
    mbedtls_gcm_free(&gcm);
    free(decoded);
    return "";
  }
  
  // Add context as additional authenticated data
  const char* aadData = context.c_str();
  size_t aadLen = context.length();
  
  ret = mbedtls_gcm_auth_decrypt(&gcm, encryptedLen,
                                iv, AES_IV_SIZE,
                                (const unsigned char*)aadData, aadLen,
                                tag, AES_TAG_SIZE,
                                encryptedData, output);
  
  mbedtls_gcm_free(&gcm);
  free(decoded);
  
  if (ret != 0) {
    Serial.printf("❌ Decryption failed (authentication error): -0x%04x\n", -ret);
    return "";
  }
  
  output[encryptedLen] = '\0';
  String result = String((char*)output);
  
  Serial.printf("🔓 Data decrypted (%d -> %d bytes)\n", ciphertext.length(), result.length());
  return result;
}

// Secure storage functions
bool storeSecureData(const String& key, const String& data, const String& context) {
  String encrypted = encryptData(data, context);
  if (encrypted.length() == 0) {
    Serial.printf("❌ Failed to encrypt data for key: %s\n", key.c_str());
    return false;
  }
  
  size_t stored = securePrefs.putString(key.c_str(), encrypted);
  if (stored == 0) {
    Serial.printf("❌ Failed to store encrypted data for key: %s\n", key.c_str());
    return false;
  }
  
  Serial.printf("🔒 Securely stored data for key: %s\n", key.c_str());
  return true;
}

String retrieveSecureData(const String& key, const String& context) {
  String encrypted = securePrefs.getString(key.c_str(), "");
  if (encrypted.length() == 0) {
    Serial.printf("⚠️ No encrypted data found for key: %s\n", key.c_str());
    return "";
  }
  
  String decrypted = decryptData(encrypted, context);
  if (decrypted.length() == 0) {
    Serial.printf("❌ Failed to decrypt data for key: %s\n", key.c_str());
    return "";
  }
  
  Serial.printf("🔓 Retrieved secure data for key: %s\n", key.c_str());
  return decrypted;
}

bool removeSecureData(const String& key) {
  bool removed = securePrefs.remove(key.c_str());
  if (removed) {
    Serial.printf("🗑️ Removed secure data for key: %s\n", key.c_str());
  } else {
    Serial.printf("⚠️ Failed to remove secure data for key: %s\n", key.c_str());
  }
  return removed;
}

// Key rotation functionality
bool rotateEncryptionKeys() {
  Serial.println("🔄 Starting encryption key rotation...");
  
  if (!encryptionInitialized) {
    Serial.println("❌ Encryption manager not initialized");
    return false;
  }
  
  // Backup current master key
  uint8_t oldMasterKey[ENCRYPTION_KEY_SIZE];
  memcpy(oldMasterKey, masterKey, ENCRYPTION_KEY_SIZE);
  
  uint8_t oldStorageKey[ENCRYPTION_KEY_SIZE];
  memcpy(oldStorageKey, storageKey, ENCRYPTION_KEY_SIZE);
  
  // Generate new master key
  int ret = mbedtls_ctr_drbg_random(&ctr_drbg, masterKey, ENCRYPTION_KEY_SIZE);
  if (ret != 0) {
    Serial.printf("❌ Failed to generate new master key: -0x%04x\n", -ret);
    // Restore old key
    memcpy(masterKey, oldMasterKey, ENCRYPTION_KEY_SIZE);
    return false;
  }
  
  // Derive new storage key
  deriveStorageKey();
  
  // Re-encrypt all stored data with new key
  // Note: This is a simplified example. In practice, you'd need to enumerate all keys
  String testKey = "device_config";
  String testData = retrieveSecureData(testKey, "system");
  
  if (testData.length() > 0) {
    // Remove old encrypted data
    securePrefs.remove(testKey.c_str());
    
    // Store with new encryption
    if (!storeSecureData(testKey, testData, "system")) {
      Serial.println("❌ Failed to re-encrypt data with new key");
      // Restore old keys
      memcpy(masterKey, oldMasterKey, ENCRYPTION_KEY_SIZE);
      memcpy(storageKey, oldStorageKey, ENCRYPTION_KEY_SIZE);
      return false;
    }
  }
  
  // Store new master key
  size_t stored = securePrefs.putBytes("master_key", masterKey, ENCRYPTION_KEY_SIZE);
  if (stored != ENCRYPTION_KEY_SIZE) {
    Serial.println("❌ Failed to store new master key");
    // Restore old keys
    memcpy(masterKey, oldMasterKey, ENCRYPTION_KEY_SIZE);
    memcpy(storageKey, oldStorageKey, ENCRYPTION_KEY_SIZE);
    return false;
  }
  
  Serial.println("✅ Encryption key rotation completed successfully");
  return true;
}

// Secure memory cleanup
void secureMemoryClear(void* ptr, size_t size) {
  if (ptr && size > 0) {
    volatile uint8_t* p = (volatile uint8_t*)ptr;
    for (size_t i = 0; i < size; i++) {
      p[i] = 0;
    }
  }
}

void cleanupEncryptionManager() {
  Serial.println("🧹 Cleaning up Encryption Manager...");
  
  // Clear sensitive data from memory
  secureMemoryClear(masterKey, ENCRYPTION_KEY_SIZE);
  secureMemoryClear(storageKey, ENCRYPTION_KEY_SIZE);
  
  // Cleanup mbedTLS contexts
  mbedtls_ctr_drbg_free(&ctr_drbg);
  mbedtls_entropy_free(&entropy);
  
  // Close preferences
  securePrefs.end();
  
  encryptionInitialized = false;
  
  Serial.println("✅ Encryption Manager cleanup completed");
}