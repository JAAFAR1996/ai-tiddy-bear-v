/*
 * BLE Provisioning Header for AI Teddy Bear ESP32-S3
 * Secure provisioning with AES-256-GCM encryption
 * 
 * Features:
 * - Nordic UART Service implementation
 * - AES-256-GCM decryption with mbedtls
 * - 10-minute timeout handling
 * - MTU 247+ bytes support
 * - Memory-safe operations
 * 
 * Author: Expert ESP32 Engineer (1000 years experience)
 * Version: 1.0.0
 */

#ifndef BLE_PROVISIONING_H
#define BLE_PROVISIONING_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "esp_err.h"
#include "esp_gatt_defs.h"

#ifdef __cplusplus
extern "C" {
#endif

// Constants
#define BLE_MAX_PAYLOAD_SIZE        512     // Maximum encrypted payload size
#define BLE_MAX_RESPONSE_SIZE       64      // Maximum response size
#define BLE_MTU_SIZE               247      // Minimum MTU for 512-byte payloads
#define BLE_PROVISIONING_TIMEOUT_MS (10 * 60 * 1000)  // 10 minutes

// Nordic UART Service UUIDs (as strings for reference)
#define UART_SERVICE_UUID_STR       "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define UART_WRITE_CHAR_UUID_STR    "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define UART_NOTIFY_CHAR_UUID_STR   "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

// Missing UUID declarations (needed for GATT database)
static const uint16_t primary_service_uuid = ESP_GATT_UUID_PRI_SERVICE;
static const uint16_t character_declaration_uuid = ESP_GATT_UUID_CHAR_DECLARE;
static const uint16_t character_client_config_uuid = ESP_GATT_UUID_CHAR_CLIENT_CONFIG;

// Missing characteristic properties (needed for GATT database)
static const uint8_t char_prop_write = ESP_GATT_CHAR_PROP_BIT_WRITE;
static const uint8_t char_prop_notify = ESP_GATT_CHAR_PROP_BIT_NOTIFY;

// BLE Packet Structure (matches documentation)
typedef struct __attribute__((packed)) {
    uint8_t nonce[12];      // 96-bit random nonce
    uint8_t tag[16];        // 128-bit authentication tag  
    uint8_t ciphertext[];   // Variable length encrypted JSON payload
} ble_packet_t;

// Provisioning Data Structure
typedef struct {
    char ssid[64];          // WiFi SSID (max 63 chars + null terminator)
    char password[64];      // WiFi password (8-63 chars + null terminator)
    char child_id[37];      // UUID format: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    char pairing_code[16];  // Pairing code from /pair/init (e.g., "A1-B2-C3")
    int child_age;          // Child age (0-18, -1 = not set)
} provisioning_data_t;

// Provisioning Result Codes
typedef enum {
    BLE_PROV_SUCCESS = 0,       // Provisioning completed successfully
    BLE_PROV_TIMEOUT,           // 10-minute timeout expired
    BLE_PROV_DECRYPT_ERROR,     // Failed to decrypt payload
    BLE_PROV_INVALID_DATA,      // Invalid credential format
    BLE_PROV_SAVE_ERROR,        // Failed to save credentials
    BLE_PROV_CONNECTION_ERROR,  // BLE connection issues
    BLE_PROV_INTERNAL_ERROR     // Internal system error
} ble_provisioning_result_t;

// Provisioning Callback Function Type
typedef void (*ble_provisioning_callback_t)(ble_provisioning_result_t result, 
                                             const provisioning_data_t* data);

/*
 * Public API Functions
 */

/**
 * Initialize BLE Provisioning System
 * Sets up BLE stack, GATT services, and security components
 * 
 * @return true if initialization successful, false otherwise
 */
bool initBLEProvisioning(void);

/**
 * Start BLE Provisioning with PoP Key
 * Begins advertising and accepts provisioning connections
 * 
 * @param pop_key 32-byte PoP key from /pair/init response (base64 decoded)
 * @param key_len Length of PoP key (must be 32)
 * @param callback Callback function for provisioning events
 * @return true if started successfully, false otherwise
 */
bool startBLEProvisioning(const uint8_t* pop_key, size_t key_len, 
                          ble_provisioning_callback_t callback);

/**
 * Handle Incoming BLE Provisioning Data
 * Processes encrypted provisioning payload from mobile app
 * 
 * @param data Raw encrypted packet data
 * @param length Length of packet data
 */
void handleBLEProvisioningData(uint8_t* data, size_t length);

/**
 * Decrypt BLE Provisioning Payload
 * Decrypts AES-256-GCM encrypted JSON payload
 * 
 * @param packet Encrypted packet structure
 * @param pop_key 32-byte PoP key for decryption
 * @param json_output Buffer for decrypted JSON (must be large enough)
 * @return true if decryption successful, false otherwise
 */
bool decryptProvisioningPayload(ble_packet_t* packet, uint8_t* pop_key, char* json_output);

/**
 * Send BLE Response to Client
 * Sends JSON response via notify characteristic
 * 
 * @param response JSON response string (max 64 bytes)
 */
void sendBLEResponse(const char* response);

/**
 * Stop BLE Provisioning
 * Stops advertising, disconnects clients, and cleans up resources
 */
void stopBLEProvisioning(void);

/**
 * Set PoP Key for Provisioning
 * Updates the decryption key during runtime
 * 
 * @param pop_key 32-byte PoP key (base64 decoded)
 * @param key_len Length of key (must be 32)
 * @return true if key set successfully, false otherwise
 */
bool setBLEPoP(const uint8_t* pop_key, size_t key_len);

/**
 * Check if BLE Provisioning is Active
 * 
 * @return true if provisioning is currently active, false otherwise
 */
bool isBLEProvisioningActive(void);

/*
 * Standard Response Messages
 */

// Success responses
#define BLE_RESPONSE_OK             "{\"status\":\"ok\",\"next\":\"connect_wifi\"}"
#define BLE_RESPONSE_RECEIVED       "{\"status\":\"received\"}"

// Error responses  
#define BLE_RESPONSE_INVALID_PACKET "{\"status\":\"error\",\"code\":\"invalid_packet\"}"
#define BLE_RESPONSE_NO_POP_KEY     "{\"status\":\"error\",\"code\":\"no_pop_key\"}"
#define BLE_RESPONSE_DECRYPT_FAILED "{\"status\":\"error\",\"code\":\"decryption_failed\"}"
#define BLE_RESPONSE_INVALID_CREDS  "{\"status\":\"error\",\"code\":\"invalid_credentials\"}"
#define BLE_RESPONSE_SAVE_FAILED    "{\"status\":\"error\",\"code\":\"save_failed\"}"
#define BLE_RESPONSE_INTERNAL_ERROR "{\"status\":\"error\",\"code\":\"internal_error\"}"

/*
 * Utility Macros
 */

// Validate packet size
#define BLE_PACKET_MIN_SIZE (sizeof(ble_packet_t))
#define BLE_PACKET_MAX_SIZE (BLE_MAX_PAYLOAD_SIZE)

// Check if packet size is valid
#define IS_VALID_PACKET_SIZE(size) \
    ((size) >= BLE_PACKET_MIN_SIZE && (size) <= BLE_PACKET_MAX_SIZE)

// Calculate ciphertext length from total packet size
#define GET_CIPHERTEXT_LEN(total_size) \
    ((total_size) - sizeof(ble_packet_t))

// Validate PoP key
#define IS_VALID_POP_KEY(key, len) \
    ((key) != NULL && (len) == 32)

// Validate SSID
#define IS_VALID_SSID(ssid) \
    ((ssid) != NULL && strlen(ssid) > 0 && strlen(ssid) <= 32)

// Validate password
#define IS_VALID_WIFI_PASSWORD(pass) \
    ((pass) != NULL && strlen(pass) >= 8 && strlen(pass) <= 63)

// Validate UUID format (basic check)
#define IS_VALID_UUID(uuid) \
    ((uuid) != NULL && strlen(uuid) == 36 && (uuid)[8] == '-' && \
     (uuid)[13] == '-' && (uuid)[18] == '-' && (uuid)[23] == '-')

/*
 * Debug Macros (only in debug builds)
 */
#ifdef CONFIG_BLE_PROV_DEBUG
    #define BLE_PROV_LOGI(tag, format, ...) ESP_LOGI(tag, format, ##__VA_ARGS__)
    #define BLE_PROV_LOGW(tag, format, ...) ESP_LOGW(tag, format, ##__VA_ARGS__)
    #define BLE_PROV_LOGE(tag, format, ...) ESP_LOGE(tag, format, ##__VA_ARGS__)
#else
    #define BLE_PROV_LOGI(tag, format, ...)
    #define BLE_PROV_LOGW(tag, format, ...)
    #define BLE_PROV_LOGE(tag, format, ...) ESP_LOGE(tag, format, ##__VA_ARGS__)
#endif

/*
 * Error Code Definitions
 */
#define BLE_PROV_ERR_BASE           0x8000
#define BLE_PROV_ERR_NOT_INIT       (BLE_PROV_ERR_BASE + 1)
#define BLE_PROV_ERR_ALREADY_ACTIVE (BLE_PROV_ERR_BASE + 2)
#define BLE_PROV_ERR_INVALID_KEY    (BLE_PROV_ERR_BASE + 3)
#define BLE_PROV_ERR_DECRYPT_FAIL   (BLE_PROV_ERR_BASE + 4)
#define BLE_PROV_ERR_INVALID_DATA   (BLE_PROV_ERR_BASE + 5)
#define BLE_PROV_ERR_SAVE_FAIL      (BLE_PROV_ERR_BASE + 6)
#define BLE_PROV_ERR_TIMEOUT        (BLE_PROV_ERR_BASE + 7)
#define BLE_PROV_ERR_NO_MEMORY      (BLE_PROV_ERR_BASE + 8)

/*
 * Configuration Options
 */

// Enable/disable features (set in menuconfig or build flags)
#ifndef CONFIG_BLE_PROV_MAX_RETRY_COUNT
#define CONFIG_BLE_PROV_MAX_RETRY_COUNT 3
#endif

#ifndef CONFIG_BLE_PROV_CONN_TIMEOUT_MS  
#define CONFIG_BLE_PROV_CONN_TIMEOUT_MS 30000
#endif

#ifndef CONFIG_BLE_PROV_ENABLE_SECURITY_LOGS
#define CONFIG_BLE_PROV_ENABLE_SECURITY_LOGS 0
#endif

// Memory allocation settings
#ifndef CONFIG_BLE_PROV_STACK_SIZE
#define CONFIG_BLE_PROV_STACK_SIZE 4096
#endif

#ifndef CONFIG_BLE_PROV_PRIORITY
#define CONFIG_BLE_PROV_PRIORITY 5
#endif

/*
 * Version Information
 */
#define BLE_PROV_VERSION_MAJOR  1
#define BLE_PROV_VERSION_MINOR  0
#define BLE_PROV_VERSION_PATCH  0
#define BLE_PROV_VERSION_STRING "1.0.0"

/*
 * Compatibility Definitions
 */
#ifdef ESP_IDF_VERSION_MAJOR
    #if ESP_IDF_VERSION_MAJOR >= 5
        #define BLE_PROV_IDF_V5_COMPAT 1
    #else
        #define BLE_PROV_IDF_V5_COMPAT 0
    #endif
#else
    #define BLE_PROV_IDF_V5_COMPAT 0
#endif

#ifdef __cplusplus
}
#endif

#endif /* BLE_PROVISIONING_H */