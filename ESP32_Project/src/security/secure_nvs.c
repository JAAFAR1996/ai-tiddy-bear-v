#include "esp_log.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "mbedtls/sha256.h"
#include <string.h>
#include "esp_system.h"
#include "esp_mac.h"

static const char *TAG = "SECURE_NVS";
static const char *NVS_NAMESPACE = "teddy_secure";

// Forward declaration
esp_err_t load_device_id(char *device_id, size_t *id_len);

// Production-grade OOB Secret Generation (matching server algorithm)
esp_err_t generate_oob_secret(const char *device_id, uint8_t *secret_out, size_t secret_len) {
    if (!device_id || !secret_out || secret_len < 32) {
        return ESP_ERR_INVALID_ARG;
    }
    
    // Same algorithm as server: SHA256(SHA256(device_id:salt) + salt)
    const char *salt = "ai-teddy-bear-oob-secret-v1";
    char hash_input[128];
    snprintf(hash_input, sizeof(hash_input), "%s:%s", device_id, salt);
    
    // First SHA256
    uint8_t first_hash[32];
    mbedtls_sha256_context ctx;
    mbedtls_sha256_init(&ctx);
    mbedtls_sha256_starts(&ctx, 0); // SHA256, not SHA224
    mbedtls_sha256_update(&ctx, (uint8_t*)hash_input, strlen(hash_input));
    mbedtls_sha256_finish(&ctx, first_hash);
    mbedtls_sha256_free(&ctx);
    
    // Convert first hash to hex string
    char first_hash_hex[65];
    for (int i = 0; i < 32; i++) {
        snprintf(&first_hash_hex[i*2], 3, "%02x", first_hash[i]);
    }
    first_hash_hex[64] = '\0';
    
    // Second SHA256: first_hash_hex + salt
    char second_input[128];
    snprintf(second_input, sizeof(second_input), "%s%s", first_hash_hex, salt);
    
    mbedtls_sha256_init(&ctx);
    mbedtls_sha256_starts(&ctx, 0);
    mbedtls_sha256_update(&ctx, (uint8_t*)second_input, strlen(second_input));
    mbedtls_sha256_finish(&ctx, secret_out);
    mbedtls_sha256_free(&ctx);
    
    ESP_LOGI(TAG, "Generated OOB secret for device %.12s... (production)", device_id);
    return ESP_OK;
}

esp_err_t load_oob_secret(uint8_t *secret_out, size_t *secret_len) {
    if (!secret_out || !secret_len || *secret_len < 32) {
        return ESP_ERR_INVALID_ARG;
    }
    
    nvs_handle_t nvs_handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open NVS namespace: %s", esp_err_to_name(err));
        return err;
    }
    
    size_t required_size = 32;
    err = nvs_get_blob(nvs_handle, "oob_secret", secret_out, &required_size);
    nvs_close(nvs_handle);
    
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        ESP_LOGW(TAG, "OOB secret not found, generating new one");
        
        // Load device ID to generate secret
        char device_id[64];
        size_t device_id_len = sizeof(device_id);
        esp_err_t dev_err = load_device_id(device_id, &device_id_len);
        if (dev_err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to load device ID for OOB generation");
            return dev_err;
        }
        
        // Generate secret
        err = generate_oob_secret(device_id, secret_out, 32);
        if (err != ESP_OK) {
            return err;
        }
        
        // Save generated secret
        nvs_handle_t write_handle;
        err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &write_handle);
        if (err == ESP_OK) {
            nvs_set_blob(write_handle, "oob_secret", secret_out, 32);
            nvs_commit(write_handle);
            nvs_close(write_handle);
            ESP_LOGI(TAG, "OOB secret generated and saved");
        }
        
        *secret_len = 32;
        return ESP_OK;
    }
    
    if (err == ESP_OK) {
        *secret_len = required_size;
        ESP_LOGI(TAG, "OOB secret loaded from NVS");
    } else {
        ESP_LOGE(TAG, "Failed to load OOB secret: %s", esp_err_to_name(err));
    }
    
    return err;
}

esp_err_t load_device_id(char *device_id, size_t *id_len) {
    if (!device_id || !id_len) {
        return ESP_ERR_INVALID_ARG;
    }
    
    nvs_handle_t nvs_handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open NVS namespace: %s", esp_err_to_name(err));
        return err;
    }
    
    err = nvs_get_str(nvs_handle, "device_id", device_id, id_len);
    nvs_close(nvs_handle);
    
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        // Generate device ID from MAC address
        uint8_t mac[6];
        esp_read_mac(mac, ESP_MAC_WIFI_STA);
        snprintf(device_id, *id_len, "Teddy-ESP32-%02X%02X%02X", 
                 mac[3], mac[4], mac[5]);
        
        // Save generated device ID
        nvs_handle_t write_handle;
        err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &write_handle);
        if (err == ESP_OK) {
            nvs_set_str(write_handle, "device_id", device_id);
            nvs_commit(write_handle);
            nvs_close(write_handle);
            ESP_LOGI(TAG, "Generated device ID: %s", device_id);
        }
        
        *id_len = strlen(device_id);
        return ESP_OK;
    }
    
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "Device ID loaded: %s", device_id);
    } else {
        ESP_LOGE(TAG, "Failed to load device ID: %s", esp_err_to_name(err));
    }
    
    return err;
}

esp_err_t save_tokens(const char *access_token, const char *refresh_token) {
    if (!access_token || !refresh_token) {
        return ESP_ERR_INVALID_ARG;
    }
    
    nvs_handle_t nvs_handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open NVS namespace: %s", esp_err_to_name(err));
        return err;
    }
    
    // Save both tokens
    esp_err_t access_err = nvs_set_str(nvs_handle, "access_token", access_token);
    esp_err_t refresh_err = nvs_set_str(nvs_handle, "refresh_token", refresh_token);
    
    if (access_err == ESP_OK && refresh_err == ESP_OK) {
        err = nvs_commit(nvs_handle);
        if (err == ESP_OK) {
            ESP_LOGI(TAG, "Tokens saved successfully");
        }
    } else {
        ESP_LOGE(TAG, "Failed to save tokens - access: %s, refresh: %s", 
                 esp_err_to_name(access_err), esp_err_to_name(refresh_err));
        err = ESP_FAIL;
    }
    
    nvs_close(nvs_handle);
    return err;
}

esp_err_t load_access_token(char *token, size_t *token_len) {
    if (!token || !token_len) {
        return ESP_ERR_INVALID_ARG;
    }
    
    nvs_handle_t nvs_handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs_handle);
    if (err != ESP_OK) {
        return err;
    }
    
    err = nvs_get_str(nvs_handle, "access_token", token, token_len);
    nvs_close(nvs_handle);
    
    return err;
}

bool have_tokens(void) {
    nvs_handle_t nvs_handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs_handle);
    if (err != ESP_OK) {
        return false;
    }
    
    size_t required_size = 0;
    err = nvs_get_str(nvs_handle, "access_token", NULL, &required_size);
    nvs_close(nvs_handle);
    
    return (err == ESP_OK && required_size > 0);
}

esp_err_t initialize_secure_nvs(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "Secure NVS initialized");
    }
    
    return ret;
}
