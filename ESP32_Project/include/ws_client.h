#ifndef WS_CLIENT_H
#define WS_CLIENT_H

#include "esp_websocket_client.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_websocket_client_handle_t ws_start(const char *wss_uri, const char *bearer);
esp_err_t ws_send_text(const char *data);
void ws_stop(void);

#ifdef __cplusplus
}
#endif

#endif // WS_CLIENT_H