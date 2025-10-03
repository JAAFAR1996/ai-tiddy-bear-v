#ifndef SECURE_NVS_H
#define SECURE_NVS_H

#include "esp_err.h"
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize secure NVS storage
 * 
 * @return esp_err_t ESP_OK on success
 */
esp_err_t initialize_secure_nvs(void);

/**
 * @brief Generate OOB secret using same algorithm as server
 * 
 * @param device_id Device identifier
 * @param secret_out Buffer to store generated secret (32 bytes)
 * @param secret_len Length of secret buffer (must be >= 32)
 * @return esp_err_t ESP_OK on success
 */
esp_err_t generate_oob_secret(const char *device_id, uint8_t *secret_out, size_t secret_len);

/**
 * @brief Load OOB secret from NVS (generates if not found)
 * 
 * @param secret_out Buffer to store secret (32 bytes)
 * @param secret_len Pointer to secret length (in/out)
 * @return esp_err_t ESP_OK on success
 */
esp_err_t load_oob_secret(uint8_t *secret_out, size_t *secret_len);

/**
 * @brief Load device ID from NVS (generates from MAC if not found)
 * 
 * @param device_id Buffer to store device ID
 * @param id_len Pointer to buffer length (in/out)
 * @return esp_err_t ESP_OK on success
 */
esp_err_t load_device_id(char *device_id, size_t *id_len);

/**
 * @brief Save JWT tokens to secure NVS
 * 
 * @param access_token Access token string
 * @param refresh_token Refresh token string
 * @return esp_err_t ESP_OK on success
 */
esp_err_t save_tokens(const char *access_token, const char *refresh_token);

/**
 * @brief Load access token from NVS
 * 
 * @param token Buffer to store token
 * @param token_len Pointer to buffer length (in/out)
 * @return esp_err_t ESP_OK on success
 */
esp_err_t load_access_token(char *token, size_t *token_len);

/**
 * @brief Check if JWT tokens are stored
 * 
 * @return true if tokens are available
 * @return false if no tokens stored
 */
bool have_tokens(void);

#ifdef __cplusplus
}
#endif

#endif // SECURE_NVS_H
