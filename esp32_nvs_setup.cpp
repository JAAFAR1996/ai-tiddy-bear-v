
// Auto-generated NVS pairing code setter
// Generated at: 2025-09-19T15:56:00.097677

#include <nvs_flash.h>
#include <nvs.h>

void setupPairingCode() {
    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    
    // Open NVS namespace
    nvs_handle_t nvs_handle;
    ret = nvs_open("storage", NVS_READWRITE, &nvs_handle);
    if (ret != ESP_OK) {
        Serial.printf("❌ Error opening NVS: %s\n", esp_err_to_name(ret));
        return;
    }
    
    // Save pairing code
    const char* pairing_code = "15cca7043db75c48262244347165c61d";
    ret = nvs_set_str(nvs_handle, "ble_pairing_code", pairing_code);
    if (ret != ESP_OK) {
        Serial.printf("❌ Error saving pairing code: %s\n", esp_err_to_name(ret));
    } else {
        Serial.println("✅ Pairing code saved to NVS");
    }
    
    // Save device data
    const char* device_data = "eyJkZXZpY2VfaWQiOiJ0ZWRkeS1lc3AzMi1jY2RiYTc5NWJhYTQiLCJwYWlyaW5nX2NvZGUiOiIxNWNjYTcwNDNkYjc1YzQ4MjYyMjQ0MzQ3MTY1YzYxZCIsImNyZWF0ZWRfYXQiOiIyMDI1LTA5LTE5VDE1OjU2OjAwLjA5NzUyMyIsInN0YXR1cyI6InByb3Zpc2lvbmVkIiwidmVyc2lvbiI6IjEuMCJ9";
    ret = nvs_set_str(nvs_handle, "device_data", device_data);
    if (ret != ESP_OK) {
        Serial.printf("❌ Error saving device data: %s\n", esp_err_to_name(ret));
    } else {
        Serial.println("✅ Device data saved to NVS");
    }
    
    // Commit changes
    ret = nvs_commit(nvs_handle);
    if (ret != ESP_OK) {
        Serial.printf("❌ Error committing NVS: %s\n", esp_err_to_name(ret));
    } else {
        Serial.println("✅ NVS changes committed");
    }
    
    nvs_close(nvs_handle);
    
    // Verify the data
    verifyPairingCode();
}

void verifyPairingCode() {
    nvs_handle_t nvs_handle;
    esp_err_t ret = nvs_open("storage", NVS_READONLY, &nvs_handle);
    if (ret != ESP_OK) {
        Serial.printf("❌ Error opening NVS for verification: %s\n", esp_err_to_name(ret));
        return;
    }
    
    char pairing_code[64];
    size_t required_size = sizeof(pairing_code);
    ret = nvs_get_str(nvs_handle, "ble_pairing_code", pairing_code, &required_size);
    
    if (ret != ESP_OK) {
        Serial.printf("❌ Error reading pairing code: %s\n", esp_err_to_name(ret));
    } else {
        Serial.printf("✅ Pairing code verified: %s\n", pairing_code);
    }
    
    nvs_close(nvs_handle);
}
