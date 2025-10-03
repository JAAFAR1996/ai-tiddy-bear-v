#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "STATE_MACHINE";

typedef enum {
    BOOT,
    WIFI_OK,
    TIME_SYNCED,
    CLAIMING,
    RUNNING,
    ERROR_RECOVERY
} app_state_t;

static app_state_t current_state = BOOT;
static int error_count = 0;
static const int MAX_ERRORS = 3;

// External function declarations
extern bool wifi_is_connected(void);
extern bool time_is_set(void);
extern bool have_tokens(void);
extern esp_err_t start_ble_claiming(void);
extern esp_err_t start_websocket_connection(void);
extern void enter_deep_sleep(int seconds);

static const char* state_to_string(app_state_t state) {
    switch (state) {
        case BOOT: return "BOOT";
        case WIFI_OK: return "WIFI_OK";
        case TIME_SYNCED: return "TIME_SYNCED";
        case CLAIMING: return "CLAIMING";
        case RUNNING: return "RUNNING";
        case ERROR_RECOVERY: return "ERROR_RECOVERY";
        default: return "UNKNOWN";
    }
}

static void transition_to(app_state_t new_state) {
    if (current_state != new_state) {
        ESP_LOGI(TAG, "State: %s -> %s", state_to_string(current_state), state_to_string(new_state));
        current_state = new_state;
    }
}

void app_state_machine_tick(void) {
    switch (current_state) {
        case BOOT:
            ESP_LOGI(TAG, "Initializing system...");
            if (wifi_is_connected()) {
                transition_to(WIFI_OK);
                error_count = 0;
            } else {
                error_count++;
                if (error_count >= MAX_ERRORS) {
                    transition_to(ERROR_RECOVERY);
                }
            }
            break;
            
        case WIFI_OK:
            if (!wifi_is_connected()) {
                ESP_LOGW(TAG, "WiFi connection lost");
                transition_to(BOOT);
                break;
            }
            
            if (time_is_set()) {
                transition_to(TIME_SYNCED);
            } else {
                ESP_LOGI(TAG, "Waiting for time synchronization...");
            }
            break;
            
        case TIME_SYNCED:
            if (!wifi_is_connected()) {
                transition_to(BOOT);
                break;
            }
            
            if (!time_is_set()) {
                transition_to(WIFI_OK);
                break;
            }
            
            if (have_tokens()) {
                transition_to(RUNNING);
            } else {
                ESP_LOGI(TAG, "No tokens found, starting claiming process");
                transition_to(CLAIMING);
            }
            break;
            
        case CLAIMING:
            ESP_LOGI(TAG, "Starting BLE claiming process");
            esp_err_t err = start_ble_claiming();
            if (err == ESP_OK) {
                if (have_tokens()) {
                    ESP_LOGI(TAG, "Claiming successful, tokens obtained");
                    transition_to(RUNNING);
                } else {
                    ESP_LOGW(TAG, "Claiming in progress...");
                }
            } else {
                ESP_LOGE(TAG, "Failed to start claiming process");
                error_count++;
                if (error_count >= MAX_ERRORS) {
                    transition_to(ERROR_RECOVERY);
                }
            }
            break;
            
        case RUNNING:
            if (!wifi_is_connected() || !time_is_set()) {
                ESP_LOGW(TAG, "Prerequisites lost, returning to boot");
                transition_to(BOOT);
                break;
            }
            
            if (!have_tokens()) {
                ESP_LOGW(TAG, "Tokens lost, re-claiming");
                transition_to(CLAIMING);
                break;
            }
            
            esp_err_t ws_err = start_websocket_connection();
            if (ws_err != ESP_OK) {
                ESP_LOGE(TAG, "WebSocket connection failed");
                error_count++;
                if (error_count >= MAX_ERRORS) {
                    transition_to(ERROR_RECOVERY);
                }
            } else {
                error_count = 0;
            }
            break;
            
        case ERROR_RECOVERY:
            ESP_LOGW(TAG, "Entering error recovery mode");
            
            unsigned int backoff_time = (1U << error_count) * 1000U;
            if (backoff_time > 60000U) backoff_time = 60000U;
            
            ESP_LOGI(TAG, "Recovery backoff: %u ms", backoff_time);
            vTaskDelay(pdMS_TO_TICKS(backoff_time));
            
            error_count = 0;
            transition_to(BOOT);
            break;
            
        default:
            ESP_LOGE(TAG, "Unknown state: %d", current_state);
            transition_to(ERROR_RECOVERY);
            break;
    }
}

app_state_t app_get_current_state(void) {
    return current_state;
}

bool app_is_running(void) {
    return current_state == RUNNING;
}

void app_force_reclaim(void) {
    ESP_LOGI(TAG, "Forcing reclaim process");
    transition_to(CLAIMING);
}