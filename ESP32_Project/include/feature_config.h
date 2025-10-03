#ifndef FEATURE_CONFIG_H
#define FEATURE_CONFIG_H

/*
🔵 AI TEDDY BEAR - FEATURE CONFIGURATION
=======================================
Strategic feature control for MVP and production builds.

PRIORITY LEVELS:
- CORE (P1): Essential for basic functionality
- IMPORTANT (P2): Required for production but not MVP
- OPTIONAL (P3): Can be disabled for troubleshooting
- FUTURE (P4): Development/experimental features
*/

// ==== CORE FEATURES (P1) - Always Required ====
#define FEATURE_WIFI_MANAGER            1    // Essential for connectivity
#define FEATURE_WEBSOCKET_CLIENT        1    // Core communication
#define FEATURE_AUDIO_HANDLER          1    // Core teddy bear functionality
#define FEATURE_HARDWARE_CONTROL       1    // LED/Button/Sensors
#define FEATURE_CONFIG_MANAGER         1    // Configuration management
#define FEATURE_MONITORING             1    // Basic system health

// ==== IMPORTANT FEATURES (P2) - Production Required ====
#define FEATURE_OTA_UPDATES            1    // Required for production updates
#define FEATURE_DEVICE_MANAGEMENT      1    // Required for fleet management
#define FEATURE_SECURITY_MANAGER       1    // Security and authentication
#define FEATURE_RESOURCE_MANAGER       1    // Memory and resource tracking

// ==== OPTIONAL FEATURES (P3) - Can Disable for MVP ====
#ifndef MVP_BUILD
  #define FEATURE_TLS_CERTIFICATE_MANAGER  1    // Advanced SSL/TLS management
  #define FEATURE_PRODUCTION_CONFIG_VALIDATOR 1  // Advanced config validation
  #define FEATURE_JWT_MANAGER             1    // Token-based authentication
  #define FEATURE_BLE_PROVISIONING        1    // Bluetooth setup alternative
  #define FEATURE_ENCRYPTION_MANAGER      1    // Advanced encryption features
  // Audio playback (speaker) path. For capture-and-send only devices, keep 0 to save RAM/CPU.
  #define FEATURE_AUDIO_PLAYBACK          0
#else
  // MVP Build - Disable optional features
  #define FEATURE_TLS_CERTIFICATE_MANAGER  0
  #define FEATURE_PRODUCTION_CONFIG_VALIDATOR 0
  #define FEATURE_JWT_MANAGER             0
  #define FEATURE_BLE_PROVISIONING        0
  #define FEATURE_ENCRYPTION_MANAGER      0
  #define FEATURE_AUDIO_PLAYBACK          0
#endif

// Audio input selection: 1 = built-in ADC (analog mic via amplifier), 0 = external I2S mic
#ifndef FEATURE_AUDIO_ADC_INPUT
#define FEATURE_AUDIO_ADC_INPUT 1
#endif

// Default ADC channel for analog mic (GPIO34 = ADC1_CHANNEL_6). Keep on ADC1 (ADC2 conflicts with WiFi)
#ifndef AUDIO_ADC_CHANNEL
#define AUDIO_ADC_CHANNEL ADC1_CHANNEL_6
#endif

// ==== FUTURE/EXPERIMENTAL FEATURES (P4) - Disable by Default ====
#define FEATURE_REALTIME_AUDIO_STREAMER 0    // Experimental streaming (high memory)
#define FEATURE_INTRUSION_DETECTION     0    // Security monitoring (experimental)
#define FEATURE_AUTO_GARBAGE_COLLECTOR  0    // Aggressive memory management
#define FEATURE_ADVANCED_MEMORY_MANAGER 0    // Complex memory optimization
#define FEATURE_CPU_MEMORY_OPTIMIZER    0    // Performance optimization
#define FEATURE_SECURE_BOOT_VALIDATOR   0    // Hardware security validation

// ==== DEBUGGING/DEVELOPMENT FEATURES ====
#ifdef DEBUG_BUILD
  #define FEATURE_PERFORMANCE_MONITOR   1    // Performance debugging
  #define FEATURE_PERFORMANCE_COMMANDS  1    // Debug commands
#else
  #define FEATURE_PERFORMANCE_MONITOR   0
  #define FEATURE_PERFORMANCE_COMMANDS  0
#endif

// ==== FEATURE DEPENDENCIES ====
// Automatically disable dependent features when core features are disabled

#if !FEATURE_SECURITY_MANAGER
  #undef FEATURE_JWT_MANAGER
  #define FEATURE_JWT_MANAGER 0
  #undef FEATURE_ENCRYPTION_MANAGER
  #define FEATURE_ENCRYPTION_MANAGER 0
#endif

#if !FEATURE_AUDIO_HANDLER
  #undef FEATURE_REALTIME_AUDIO_STREAMER
  #define FEATURE_REALTIME_AUDIO_STREAMER 0
#endif

// ==== MEMORY OPTIMIZATION BASED ON FEATURES ====
#if FEATURE_REALTIME_AUDIO_STREAMER
  #define AUDIO_BUFFER_SIZE 8192
  #define MAX_CONCURRENT_STREAMS 2
#else
  #define AUDIO_BUFFER_SIZE 2048
  #define MAX_CONCURRENT_STREAMS 1
#endif

// ==== FEATURE VALIDATION ====
// Ensure at least core features are enabled
#if !FEATURE_WIFI_MANAGER || !FEATURE_WEBSOCKET_CLIENT || !FEATURE_AUDIO_HANDLER
  #error "Core features cannot be disabled. Check FEATURE_* definitions."
#endif

// ==== FEATURE STATUS REPORTING ====
void printFeatureConfiguration() {
  Serial.println("=== 🔵 Feature Configuration ===");
  Serial.println("CORE FEATURES (P1):");
  Serial.printf("  WiFi Manager: %s\n", FEATURE_WIFI_MANAGER ? "✅" : "❌");
  Serial.printf("  WebSocket Client: %s\n", FEATURE_WEBSOCKET_CLIENT ? "✅" : "❌");
  Serial.printf("  Audio Handler: %s\n", FEATURE_AUDIO_HANDLER ? "✅" : "❌");
  Serial.printf("  Hardware Control: %s\n", FEATURE_HARDWARE_CONTROL ? "✅" : "❌");
  
  Serial.println("PRODUCTION FEATURES (P2):");
  Serial.printf("  OTA Updates: %s\n", FEATURE_OTA_UPDATES ? "✅" : "❌");
  Serial.printf("  Security Manager: %s\n", FEATURE_SECURITY_MANAGER ? "✅" : "❌");
  Serial.printf("  Device Management: %s\n", FEATURE_DEVICE_MANAGEMENT ? "✅" : "❌");
  
  Serial.println("OPTIONAL FEATURES (P3):");
  Serial.printf("  TLS Certificate Manager: %s\n", FEATURE_TLS_CERTIFICATE_MANAGER ? "✅" : "❌");
  Serial.printf("  Production Config Validator: %s\n", FEATURE_PRODUCTION_CONFIG_VALIDATOR ? "✅" : "❌");
  Serial.printf("  JWT Manager: %s\n", FEATURE_JWT_MANAGER ? "✅" : "❌");
  
  Serial.println("EXPERIMENTAL FEATURES (P4):");
  Serial.printf("  Realtime Audio Streamer: %s\n", FEATURE_REALTIME_AUDIO_STREAMER ? "✅" : "❌");
  Serial.printf("  Intrusion Detection: %s\n", FEATURE_INTRUSION_DETECTION ? "✅" : "❌");
}

#endif // FEATURE_CONFIG_H
