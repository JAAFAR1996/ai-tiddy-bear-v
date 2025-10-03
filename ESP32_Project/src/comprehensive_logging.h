#ifndef COMPREHENSIVE_LOGGING_H
#define COMPREHENSIVE_LOGGING_H

#include <Arduino.h>

// ========================================
// 🧸 AI TEDDY BEAR - COMPREHENSIVE LOGGING
// ========================================
// نظام logging شامل لتتبع جميع الأحداث والتفاعلات
// Comprehensive logging system for tracking all events and interactions

// Event Categories
#define LOG_AUTH      "[AUTH]"
#define LOG_AUDIO     "[AUDIO]"
#define LOG_WS        "[WS]"
#define LOG_HTTP      "[HTTP]"
#define LOG_WIFI      "[WIFI]"
#define LOG_SECURITY  "[SEC]"
#define LOG_SYSTEM    "[SYS]"
#define LOG_BUTTON    "[BTN]"
#define LOG_SENSOR    "[SENSOR]"
#define LOG_LED       "[LED]"
#define LOG_ERROR     "[ERROR]"
#define LOG_SUCCESS   "[SUCCESS]"

// Audio Flow States
#define AUDIO_FLOW_IDLE        "🎵 IDLE"
#define AUDIO_FLOW_RECORDING   "🎤 RECORDING"
#define AUDIO_FLOW_SENDING     "📤 SENDING"
#define AUDIO_FLOW_PROCESSING  "⚙️ PROCESSING"
#define AUDIO_FLOW_RECEIVING   "📥 RECEIVING"
#define AUDIO_FLOW_PLAYING     "🔊 PLAYING"
#define AUDIO_FLOW_COMPLETE    "✅ COMPLETE"

// WebSocket Flow States
#define WS_FLOW_DISCONNECTED   "🔌 DISCONNECTED"
#define WS_FLOW_CONNECTING     "🔗 CONNECTING"
#define WS_FLOW_CONNECTED      "✅ CONNECTED"
#define WS_FLOW_AUTHENTICATING "🔐 AUTHENTICATING"
#define WS_FLOW_AUTHENTICATED  "🔓 AUTHENTICATED"
#define WS_FLOW_SENDING        "📤 SENDING"
#define WS_FLOW_RECEIVING      "📥 RECEIVING"
#define WS_FLOW_ERROR          "❌ ERROR"

// Authentication Flow States
#define AUTH_FLOW_NONE         "❌ NONE"
#define AUTH_FLOW_PENDING      "⏳ PENDING"
#define AUTH_FLOW_VALID        "✅ VALID"
#define AUTH_FLOW_FAILED       "❌ FAILED"
#define AUTH_FLOW_EXPIRED      "⏰ EXPIRED"

// ========================================
// 🎯 MAIN EVENT LOGGING FUNCTIONS
// ========================================

// Audio Event Logging
void logAudioEvent(const String& event, const String& details = "");
void logAudioFlowState(const String& state, const String& info = "");
void logAudioData(const String& operation, size_t bytes, const String& format = "");

// WebSocket Event Logging
void logWebSocketEvent(const String& event, const String& details = "");
void logWebSocketFlowState(const String& state, const String& info = "");
void logWebSocketMessage(const String& direction, const String& type, size_t size = 0);

// Authentication Event Logging
void logAuthEvent(const String& event, const String& details = "");
void logAuthFlowState(const String& state, const String& info = "");
void logAuthToken(const String& operation, const String& status = "");

// System Event Logging
void logSystemEvent(const String& event, const String& details = "");
void logButtonEvent(const String& action, const String& result = "");
void logSensorEvent(const String& sensor, const String& value = "");

// Error and Success Logging
void logError(const String& component, const String& error, const String& details = "");
void logSuccess(const String& component, const String& success, const String& details = "");

// ========================================
// 🔄 COMPLETE FLOW TRACKING
// ========================================

// Complete Audio Interaction Flow
void logCompleteAudioFlow(const String& phase, const String& status, const String& details = "");

// Complete Authentication Flow
void logCompleteAuthFlow(const String& phase, const String& status, const String& details = "");

// Complete WebSocket Flow
void logCompleteWebSocketFlow(const String& phase, const String& status, const String& details = "");

// ========================================
// 📊 STATISTICS AND METRICS
// ========================================

// Audio Statistics
void logAudioStats(size_t bytesRecorded, size_t bytesSent, size_t bytesReceived, size_t bytesPlayed);
void logAudioQuality(float rmsLevel, int16_t peakLevel, bool voiceDetected);

// Network Statistics
void logNetworkStats(const String& operation, unsigned long duration, size_t bytes, bool success);

// System Statistics
void logSystemStats(unsigned long uptime, size_t freeHeap, float cpuUsage);

// ========================================
// 🎭 USER INTERACTION LOGGING
// ========================================

// Button Interactions
void logButtonInteraction(const String& action, const String& context, const String& result);

// LED Animations
void logLEDAnimation(const String& animation, const String& color, int duration);

// Audio Playback
void logAudioPlayback(const String& audioType, int volume, int duration, bool success);

// ========================================
// 🔧 DEBUGGING HELPERS
// ========================================

// JSON Parsing
void logJSONParse(const String& operation, bool success, const String& error = "");

// Memory Management
void logMemoryOperation(const String& operation, size_t bytes, bool success);

// Timing Information
void logTiming(const String& operation, unsigned long startTime, unsigned long endTime);

// ========================================
// 📋 FLOW STATE TRACKING
// ========================================

// Global flow state variables (extern)
extern String currentAudioFlowState;
extern String currentWebSocketFlowState;
extern String currentAuthFlowState;
extern String currentSystemState;

// Flow state management
void updateAudioFlowState(const String& newState);
void updateWebSocketFlowState(const String& newState);
void updateAuthFlowState(const String& newState);
void updateSystemState(const String& newState);

// Flow state logging
void logCurrentFlowStates();

#endif // COMPREHENSIVE_LOGGING_H
