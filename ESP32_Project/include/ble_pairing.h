#ifndef BLE_PAIRING_H
#define BLE_PAIRING_H

#include "esp_err.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t ble_pairing_init(void);
int compute_claim_hmac(const uint8_t *oob_secret, size_t secret_len,
                       const char *device_id, const char *child_id,
                       const uint8_t *nonce, size_t nonce_len,
                       uint8_t out[32]);
bool verify_claim_signature(const char *device_id, const char *child_id, 
                           const uint8_t *nonce, size_t nonce_len,
                           const uint8_t *signature, const uint8_t *oob_secret);

#ifdef __cplusplus
}
#endif

#endif // BLE_PAIRING_H