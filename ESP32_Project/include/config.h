#ifndef CONFIG_H
#define CONFIG_H

// System configuration
#define SYSTEM_CHECK_INTERVAL 30000    // Check system health every 30 seconds
#define PRODUCTION_MODE true
#define USE_SSL true
#define ENABLE_OTA true
#define ENABLE_WIFI_MANAGER true

// Network Configuration - Production defaults
#define DEFAULT_SERVER_HOST "ai-teddy-backend.herokuapp.com"  // أو سيرفرك
#define DEFAULT_SERVER_PORT 443  // HTTPS
#define DEFAULT_WEBSOCKET_PATH "/ws"
#define DEFAULT_USE_SSL true

// Network Configuration - will be set via WiFiManager
extern const char* WIFI_SSID;
extern const char* WIFI_PASSWORD;
extern const char* SERVER_HOST;
extern const int SERVER_PORT;
extern const char* WEBSOCKET_PATH;

// SSL Configuration
#define SSL_PORT 443
#define SSL_FINGERPRINT "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD"

// Device Security - will be generated at runtime
extern String deviceSecretKey;
#define API_VERSION "v1"
#define FIRMWARE_UPDATE_URL "https://your-server.com/api/v1/firmware"

// ... جميع الـ #define تبقى كما هي، لا تغيرها

#define LED_PIN 2
#define SERVO_PIN 18
#define SPEAKER_PIN 25
#define BUTTON_PIN 0
#define MIC_PIN 34
#define I2S_WS 22
#define I2S_SD 21
#define I2S_SCK 26

#define NUM_LEDS 10
#define LED_BRIGHTNESS 50

#define DEVICE_ID "teddy_bear_001"
#define FIRMWARE_VERSION "1.0.0"

#define DEBOUNCE_DELAY 200
#define HEARTBEAT_INTERVAL 30000
#define RECONNECT_INTERVAL 10000

#define FREQ_HAPPY 1500
#define FREQ_SAD 500
#define FREQ_EXCITED 2000
#define FREQ_DEFAULT 1000

#define SERVO_CENTER 90
#define SERVO_LEFT 45
#define SERVO_RIGHT 135
#define SERVO_UP 60
#define SERVO_DOWN 120

#endif
