#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>
#include <ArduinoJson.h>

// Configuration versioning
#define CONFIG_VERSION_MAJOR 2
#define CONFIG_VERSION_MINOR 0
#define CONFIG_VERSION_PATCH 1
#define CONFIG_VERSION_STRING "2.0.1"
#define CONFIG_SCHEMA_VERSION 1

// Hardware pins (additional definitions)
#ifndef DEBOUNCE_DELAY
#define DEBOUNCE_DELAY 200
#endif

// Server configuration will be set at runtime via extern declarations below

// Environment detection
#ifndef BUILD_ENV
#define BUILD_ENV "production"  // Default to production
#endif

// Environment-specific base configurations
#ifdef PRODUCTION_BUILD
  #define ENVIRONMENT_MODE "production"
  #define SYSTEM_CHECK_INTERVAL 60000
  #define DEFAULT_LOG_LEVEL 2  // WARN and ERROR only
  #define ENABLE_DEBUG_FEATURES false
  #define USE_SSL_DEFAULT false
  #define WATCHDOG_TIMEOUT 30000
#elif defined(STAGING_BUILD)
  #define ENVIRONMENT_MODE "staging"
  #define SYSTEM_CHECK_INTERVAL 45000
  #define DEFAULT_LOG_LEVEL 3  // INFO, WARN, ERROR
  #define ENABLE_DEBUG_FEATURES true
  #define USE_SSL_DEFAULT true
  #define WATCHDOG_TIMEOUT 45000
#else
  #define ENVIRONMENT_MODE "development"
  #define SYSTEM_CHECK_INTERVAL 15000
  #define DEFAULT_LOG_LEVEL 4  // DEBUG, INFO, WARN, ERROR
  #define ENABLE_DEBUG_FEATURES true
  #define USE_SSL_DEFAULT false
  #define WATCHDOG_TIMEOUT 60000
#endif

// Dynamic system configuration
#ifndef PRODUCTION_MODE
#define PRODUCTION_MODE (strcmp(ENVIRONMENT_MODE, "production") == 0)
#endif
#ifndef USE_SSL
#define USE_SSL USE_SSL_DEFAULT
#endif
#define ENABLE_OTA true
#define ENABLE_WIFI_MANAGER true

// SSL / TLS - Environment specific
#ifdef PRODUCTION_BUILD
  #define PRODUCTION_SSL_ENABLED false  // Disable SSL for local server
  #define SSL_PORT 443
  #define SSL_FINGERPRINT "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD"
  #define DEFAULT_SSL_ENABLED false  // Disable SSL for local development
#else
  #define PRODUCTION_SSL_ENABLED false
  #define SSL_PORT 8443
  #define SSL_FINGERPRINT ""
  #define DEFAULT_SSL_ENABLED false  // Allow HTTP in development
#endif

// WiFi creds (managed by WiFiManager)
extern const char* WIFI_SSID;
extern const char* WIFI_PASSWORD;

// Environment-specific server configurations - PRODUCTION SERVER
#ifdef PRODUCTION_BUILD
  // Production server configuration
  #define DEFAULT_SERVER_HOST "localhost"
  #define DEFAULT_SERVER_PORT 8000
  #define DEFAULT_WEBSOCKET_PATH "/api/v1/esp32/chat"
  #define DEFAULT_API_BASE_URL "http://localhost:8000/api/v1"
#elif defined(STAGING_BUILD)
  #define DEFAULT_SERVER_HOST "ai-tiddy-bear-v-xuqy.onrender.com"
  #define DEFAULT_SERVER_PORT 443
  #define DEFAULT_WEBSOCKET_PATH "/api/v1/esp32/chat"
  #define DEFAULT_API_BASE_URL "https://ai-tiddy-bear-v-xuqy.onrender.com/api/v1"
#else
  // Development: connect to local FastAPI server
  #define DEFAULT_SERVER_HOST "localhost"
  #define DEFAULT_SERVER_PORT 8000
  #define DEFAULT_WEBSOCKET_PATH "/api/v1/esp32/chat"
  #define DEFAULT_API_BASE_URL "http://localhost:8000/api/v1"
#endif

// Runtime config (actual values defined in config.cpp)
extern const char* SERVER_HOST;
extern const int   SERVER_PORT;
extern const char* WEBSOCKET_PATH;

// Device / firmware (will be overridden by dynamic config)
#define DEFAULT_DEVICE_ID "teddy-001"
#define FIRMWARE_VERSION "1.2.0"
#define HARDWARE_VERSION "1.0"
#define CONFIG_FORMAT_VERSION "1.0"

// Hardware pins - Audio-Only Teddy Bear Design
// 🧸 No LEDs in teddy bear - only button and audio components
#define BUTTON_PIN 0  // Hidden button inside teddy bear
#define MIC_PIN 34    // Internal microphone

// Audio I2S Configuration - ESP32 WROOM Compatible
#define I2S_SCK 14          // Serial Clock (changed from 26 to avoid DAC conflict)
#define I2S_WS 15           // Word Select (changed from 22 for better compatibility)
#define I2S_SD 32           // Serial Data (changed from 21 for better compatibility)
#define SPEAKER_PIN 33      // Audio Output (changed from 25 to avoid DAC conflict)

// PAM8403 DAC Configuration (GPIO25/26 reserved for DAC)
#define AUDIO_OUT_LEFT   25  // DAC1 → PAM8403 L_IN
#define AUDIO_OUT_RIGHT  26  // DAC2 → PAM8403 R_IN
#ifndef AUDIO_USE_DAC
#define AUDIO_USE_DAC 0      // 0: use PWM(LEDC) on SPEAKER_PIN, 1: use DAC on GPIO25
#endif
#define RECONNECT_INTERVAL 10000
#define HEARTBEAT_INTERVAL 30000
#define DEVICE_ID DEFAULT_DEVICE_ID

// Audio frequencies
#define FREQ_HAPPY 1500
#define FREQ_SAD 500
#define FREQ_EXCITED 2000
#define FREQ_DEFAULT 1000

// LED compatibility (audio-only teddy has no LEDs)
#define NUM_LEDS 0
#define LED_BRIGHTNESS 0

// Environment-specific API endpoints - PRODUCTION SERVER
#ifdef PRODUCTION_BUILD
  // Production API endpoints
  #define DEFAULT_FIRMWARE_UPDATE_URL "http://localhost:8000/api/v1/esp32/firmware"
  #define DEFAULT_CONFIG_UPDATE_URL   "http://localhost:8000/api/v1/esp32/config"
  #define DEFAULT_CLAIM_URL           "http://localhost:8000/api/v1/pair/claim"
#elif defined(STAGING_BUILD)
  #define DEFAULT_FIRMWARE_UPDATE_URL "https://ai-tiddy-bear-v-xuqy.onrender.com/api/v1/esp32/firmware"
  #define DEFAULT_CONFIG_UPDATE_URL "https://ai-tiddy-bear-v-xuqy.onrender.com/api/v1/esp32/config"
  #define DEFAULT_CLAIM_URL "https://ai-tiddy-bear-v-xuqy.onrender.com/api/v1/pair/claim"
#else
  // Development: local HTTP endpoints
  #define DEFAULT_FIRMWARE_UPDATE_URL "http://localhost:8000/api/v1/esp32/firmware"
  #define DEFAULT_CONFIG_UPDATE_URL "http://localhost:8000/api/v1/esp32/config"
  #define DEFAULT_CLAIM_URL "http://localhost:8000/api/v1/pair/claim"
#endif

// Security / API - PRODUCTION SECURE KEYS
#ifdef PRODUCTION_BUILD
  #define DEVICE_SECRET_KEY "TeddyBear2025SecureKey7891234567890"  // SECURE 32-char key
  #define ESP32_SHARED_SECRET "5152d39be676c04613484f6545f3799bc5c37664242009528781c2db3313693e"  // ✅ Production HMAC key
#else
  #define DEVICE_SECRET_KEY "dev-secret-key-not-for-production"   // Development key
  #define ESP32_SHARED_SECRET "5152d39be676c04613484f6545f3799bc5c37664242009528781c2db3313693e"  // ✅ Same for testing
#endif

#define API_VERSION "v1"

// Configuration validation constants
#define MIN_CONFIG_VERSION 1
#define CONFIG_MAX_SIZE 4096
#define MAX_CONFIG_SIZE CONFIG_MAX_SIZE
#define CONFIG_CHECKSUM_LENGTH 32
#define CONFIG_BACKUP_COUNT 3

// Configuration update intervals
#define CONFIG_UPDATE_CHECK_INTERVAL 3600000  // 1 hour
#define CONFIG_FORCE_UPDATE_INTERVAL 86400000 // 24 hours
#define CONFIG_RETRY_INTERVAL 300000          // 5 minutes

// Configuration state tracking
struct ConfigMetadata {
  String version;
  String environment;
  String checksum;
  unsigned long lastUpdate;
  unsigned long lastValidation;
  bool isValid;
  bool needsUpdate;
  int validationErrors;
};

// Configuration validation result
struct ConfigValidationResult {
  bool isValid;
  int errorCount;
  String errors[10]; // Max 10 validation errors
  String warnings[5]; // Max 5 warnings
  int warningCount;
  float validationScore; // 0.0 - 1.0
};

// Dynamic configuration loading interface
class DynamicConfig {
public:
  static bool loadFromJSON(const String& jsonStr);
  static bool loadFromFile(const String& filename);
  static bool loadFromServer();
  static String saveToJSON();
  static bool saveToFile(const String& filename);
  
  static ConfigValidationResult validate();
  static bool applyConfiguration();
  static void rollbackConfiguration();
  
  static ConfigMetadata getMetadata();
  static String getCurrentEnvironment();
  static bool isProductionMode();
  
  static void scheduleConfigUpdate();
  static void checkForConfigUpdates();
  static void createBackup();
  static bool restoreBackup(int backupIndex = 0);
};

// Global configuration access functions
String getConfigValue(const String& key, const String& defaultValue = "");
int getConfigValueInt(const String& key, int defaultValue = 0);
bool getConfigValueBool(const String& key, bool defaultValue = false);
float getConfigValueFloat(const String& key, float defaultValue = 0.0);

bool setConfigValue(const String& key, const String& value);
bool setConfigValue(const String& key, int value);
bool setConfigValue(const String& key, bool value);
bool setConfigValue(const String& key, float value);

// Configuration event callbacks
typedef void (*ConfigUpdateCallback)(const String& key, const String& oldValue, const String& newValue);
void registerConfigUpdateCallback(ConfigUpdateCallback callback);
void unregisterConfigUpdateCallback(ConfigUpdateCallback callback);

// Environment-specific configuration overrides
void loadEnvironmentOverrides();
void applyEnvironmentDefaults();

// Configuration utilities
String generateConfigChecksum(const String& config);
bool verifyConfigIntegrity(const String& config, const String& checksum);
void logConfigurationState();
void printEnvironmentInfo();

// Production-only security validations
#ifdef PRODUCTION_BUILD
  #define VALIDATE_PRODUCTION_SECURITY() \
    do { \
      if (strcmp(DEVICE_SECRET_KEY, "your-device-secret-key-32-chars") == 0) { \
        Serial.println("💥 CRITICAL: Default secret key detected in production!"); \
        ESP.restart(); \
      } \
    } while(0)
#else
  #define VALIDATE_PRODUCTION_SECURITY()
#endif

#endif
