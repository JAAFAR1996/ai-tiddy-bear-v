#include "esp_websocket_client.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

static const char *TAG = "WS_CLIENT";
static esp_websocket_client_handle_t ws_client = NULL;

static void websocket_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data) {
    esp_websocket_event_data_t *data = (esp_websocket_event_data_t *)event_data;
    
    switch (event_id) {
        case WEBSOCKET_EVENT_CONNECTED:
            ESP_LOGI(TAG, "WebSocket connected");
            break;
        case WEBSOCKET_EVENT_DISCONNECTED:
            ESP_LOGI(TAG, "WebSocket disconnected");
            break;
        case WEBSOCKET_EVENT_DATA:
            ESP_LOGD(TAG, "Received %d bytes", data->data_len);
            break;
        case WEBSOCKET_EVENT_ERROR:
            ESP_LOGE(TAG, "WebSocket error");
            break;
        default:
            break;
    }
}

esp_websocket_client_handle_t ws_start(const char *wss_uri, const char *bearer) {
    if (!wss_uri) {
        ESP_LOGE(TAG, "Invalid URI parameter");
        return NULL;
    }
    
    esp_websocket_client_config_t cfg = {
        .uri = wss_uri,
        .skip_cert_common_name_check = true,
        .use_global_ca_store = true,
        .pingpong_timeout_sec = 30,
        .disable_auto_reconnect = false
    };
    
    // Add Authorization header only if bearer token is provided
    char auth_header[512];
    if (bearer) {
        snprintf(auth_header, sizeof(auth_header), "Authorization: Bearer %s\r\n", bearer);
        cfg.headers = auth_header;
    }
    
    ws_client = esp_websocket_client_init(&cfg);
    if (!ws_client) {
        ESP_LOGE(TAG, "Failed to initialize WebSocket client");
        return NULL;
    }
    
    esp_websocket_register_events(ws_client, WEBSOCKET_EVENT_ANY, websocket_event_handler, NULL);
    
    esp_err_t err = esp_websocket_client_start(ws_client);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start WebSocket client: %s", esp_err_to_name(err));
        esp_websocket_client_destroy(ws_client);
        ws_client = NULL;
        return NULL;
    }
    
    ESP_LOGI(TAG, "WebSocket client started");
    return ws_client;
}

esp_err_t ws_send_text(const char *data) {
    if (!ws_client || !data) return ESP_ERR_INVALID_ARG;
    return esp_websocket_client_send_text(ws_client, data, strlen(data), portMAX_DELAY);
}

void ws_stop(void) {
    if (ws_client) {
        esp_websocket_client_stop(ws_client);
        esp_websocket_client_destroy(ws_client);
        ws_client = NULL;
        ESP_LOGI(TAG, "WebSocket client stopped");
    }
}