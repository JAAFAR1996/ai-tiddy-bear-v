#ifndef CLAIM_FLOW_H
#define CLAIM_FLOW_H

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t start_ble_claiming(void);
esp_err_t handle_claim_request(const char *child_id, const char *nonce);
esp_err_t start_websocket_connection(void);

#ifdef __cplusplus
}

// C++ functions for ESP32 claim flow
String generateNonce();
String generateOOBSecret(const String& deviceId);
String calculateHMAC(const String& deviceId, const String& childId, 
                     const String& nonce, const String& oobSecret);
bool claimDevice(const String& deviceId, const String& targetChildId);

#endif

#endif // CLAIM_FLOW_H