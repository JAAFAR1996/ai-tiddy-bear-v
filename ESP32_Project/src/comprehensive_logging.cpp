#include "comprehensive_logging.h"

// ========================================
// 🔄 FLOW STATE TRACKING VARIABLES
// ========================================

String currentAudioFlowState = AUDIO_FLOW_IDLE;
String currentWebSocketFlowState = WS_FLOW_DISCONNECTED;
String currentAuthFlowState = AUTH_FLOW_NONE;
String currentSystemState = "INITIALIZING";

// ========================================
// 🎯 MAIN EVENT LOGGING FUNCTIONS
// ========================================

void logAudioEvent(const String& event, const String& details) {
    String timestamp = String(millis());
    Serial.printf("%s %s Audio Event: %s", LOG_AUDIO, timestamp.c_str(), event.c_str());
    if (details.length() > 0) {
        Serial.printf(" - %s", details.c_str());
    }
    Serial.println();
}

void logAudioFlowState(const String& state, const String& info) {
    currentAudioFlowState = state;
    String timestamp = String(millis());
    Serial.printf("%s %s Audio Flow: %s", LOG_AUDIO, timestamp.c_str(), state.c_str());
    if (info.length() > 0) {
        Serial.printf(" - %s", info.c_str());
    }
    Serial.println();
}

void logAudioData(const String& operation, size_t bytes, const String& format) {
    String timestamp = String(millis());
    Serial.printf("%s %s Audio Data: %s %d bytes", LOG_AUDIO, timestamp.c_str(), operation.c_str(), bytes);
    if (format.length() > 0) {
        Serial.printf(" (%s)", format.c_str());
    }
    Serial.println();
}

void logWebSocketEvent(const String& event, const String& details) {
    String timestamp = String(millis());
    Serial.printf("%s %s WebSocket Event: %s", LOG_WS, timestamp.c_str(), event.c_str());
    if (details.length() > 0) {
        Serial.printf(" - %s", details.c_str());
    }
    Serial.println();
}

void logWebSocketFlowState(const String& state, const String& info) {
    currentWebSocketFlowState = state;
    String timestamp = String(millis());
    Serial.printf("%s %s WebSocket Flow: %s", LOG_WS, timestamp.c_str(), state.c_str());
    if (info.length() > 0) {
        Serial.printf(" - %s", info.c_str());
    }
    Serial.println();
}

void logWebSocketMessage(const String& direction, const String& type, size_t size) {
    String timestamp = String(millis());
    Serial.printf("%s %s WebSocket Message: %s %s", LOG_WS, timestamp.c_str(), direction.c_str(), type.c_str());
    if (size > 0) {
        Serial.printf(" (%d bytes)", size);
    }
    Serial.println();
}

void logAuthEvent(const String& event, const String& details) {
    String timestamp = String(millis());
    Serial.printf("%s %s Auth Event: %s", LOG_AUTH, timestamp.c_str(), event.c_str());
    if (details.length() > 0) {
        Serial.printf(" - %s", details.c_str());
    }
    Serial.println();
}

void logAuthFlowState(const String& state, const String& info) {
    currentAuthFlowState = state;
    String timestamp = String(millis());
    Serial.printf("%s %s Auth Flow: %s", LOG_AUTH, timestamp.c_str(), state.c_str());
    if (info.length() > 0) {
        Serial.printf(" - %s", info.c_str());
    }
    Serial.println();
}

void logAuthToken(const String& operation, const String& status) {
    String timestamp = String(millis());
    Serial.printf("%s %s Token %s: %s", LOG_AUTH, timestamp.c_str(), operation.c_str(), status.c_str());
    Serial.println();
}

void logSystemEvent(const String& event, const String& details) {
    String timestamp = String(millis());
    Serial.printf("%s %s System Event: %s", LOG_SYSTEM, timestamp.c_str(), event.c_str());
    if (details.length() > 0) {
        Serial.printf(" - %s", details.c_str());
    }
    Serial.println();
}

void logButtonEvent(const String& action, const String& result) {
    String timestamp = String(millis());
    Serial.printf("%s %s Button %s: %s", LOG_BUTTON, timestamp.c_str(), action.c_str(), result.c_str());
    Serial.println();
}

void logSensorEvent(const String& sensor, const String& value) {
    String timestamp = String(millis());
    Serial.printf("%s %s Sensor %s: %s", LOG_SENSOR, timestamp.c_str(), sensor.c_str(), value.c_str());
    Serial.println();
}

void logError(const String& component, const String& error, const String& details) {
    String timestamp = String(millis());
    Serial.printf("%s %s ERROR in %s: %s", LOG_ERROR, timestamp.c_str(), component.c_str(), error.c_str());
    if (details.length() > 0) {
        Serial.printf(" - %s", details.c_str());
    }
    Serial.println();
}

void logSuccess(const String& component, const String& success, const String& details) {
    String timestamp = String(millis());
    Serial.printf("%s %s SUCCESS in %s: %s", LOG_SUCCESS, timestamp.c_str(), component.c_str(), success.c_str());
    if (details.length() > 0) {
        Serial.printf(" - %s", details.c_str());
    }
    Serial.println();
}

// ========================================
// 🔄 COMPLETE FLOW TRACKING
// ========================================

void logCompleteAudioFlow(const String& phase, const String& status, const String& details) {
    String timestamp = String(millis());
    Serial.printf("🎵 %s AUDIO FLOW - Phase: %s | Status: %s", timestamp.c_str(), phase.c_str(), status.c_str());
    if (details.length() > 0) {
        Serial.printf(" | Details: %s", details.c_str());
    }
    Serial.println();
}

void logCompleteAuthFlow(const String& phase, const String& status, const String& details) {
    String timestamp = String(millis());
    Serial.printf("🔐 %s AUTH FLOW - Phase: %s | Status: %s", timestamp.c_str(), phase.c_str(), status.c_str());
    if (details.length() > 0) {
        Serial.printf(" | Details: %s", details.c_str());
    }
    Serial.println();
}

void logCompleteWebSocketFlow(const String& phase, const String& status, const String& details) {
    String timestamp = String(millis());
    Serial.printf("🌐 %s WEBSOCKET FLOW - Phase: %s | Status: %s", timestamp.c_str(), phase.c_str(), status.c_str());
    if (details.length() > 0) {
        Serial.printf(" | Details: %s", details.c_str());
    }
    Serial.println();
}

// ========================================
// 📊 STATISTICS AND METRICS
// ========================================

void logAudioStats(size_t bytesRecorded, size_t bytesSent, size_t bytesReceived, size_t bytesPlayed) {
    String timestamp = String(millis());
    Serial.printf("📊 %s AUDIO STATS - Recorded: %d bytes | Sent: %d bytes | Received: %d bytes | Played: %d bytes", 
                  timestamp.c_str(), bytesRecorded, bytesSent, bytesReceived, bytesPlayed);
    Serial.println();
}

void logAudioQuality(float rmsLevel, int16_t peakLevel, bool voiceDetected) {
    String timestamp = String(millis());
    Serial.printf("🎯 %s AUDIO QUALITY - RMS: %.2f dBFS | Peak: %d | Voice: %s", 
                  timestamp.c_str(), rmsLevel, peakLevel, voiceDetected ? "YES" : "NO");
    Serial.println();
}

void logNetworkStats(const String& operation, unsigned long duration, size_t bytes, bool success) {
    String timestamp = String(millis());
    Serial.printf("🌐 %s NETWORK - %s | Duration: %lu ms | Bytes: %d | Success: %s", 
                  timestamp.c_str(), operation.c_str(), duration, bytes, success ? "YES" : "NO");
    Serial.println();
}

void logSystemStats(unsigned long uptime, size_t freeHeap, float cpuUsage) {
    String timestamp = String(millis());
    Serial.printf("💻 %s SYSTEM - Uptime: %lu s | Free Heap: %d bytes | CPU: %.1f%%", 
                  timestamp.c_str(), uptime, freeHeap, cpuUsage);
    Serial.println();
}

// ========================================
// 🎭 USER INTERACTION LOGGING
// ========================================

void logButtonInteraction(const String& action, const String& context, const String& result) {
    String timestamp = String(millis());
    Serial.printf("🔘 %s BUTTON - Action: %s | Context: %s | Result: %s", 
                  timestamp.c_str(), action.c_str(), context.c_str(), result.c_str());
    Serial.println();
}

void logLEDAnimation(const String& animation, const String& color, int duration) {
    String timestamp = String(millis());
    Serial.printf("💡 %s LED - Animation: %s | Color: %s | Duration: %d ms", 
                  timestamp.c_str(), animation.c_str(), color.c_str(), duration);
    Serial.println();
}

void logAudioPlayback(const String& audioType, int volume, int duration, bool success) {
    String timestamp = String(millis());
    Serial.printf("🔊 %s PLAYBACK - Type: %s | Volume: %d%% | Duration: %d ms | Success: %s", 
                  timestamp.c_str(), audioType.c_str(), volume, duration, success ? "YES" : "NO");
    Serial.println();
}

// ========================================
// 🔧 DEBUGGING HELPERS
// ========================================

void logJSONParse(const String& operation, bool success, const String& error) {
    String timestamp = String(millis());
    Serial.printf("📝 %s JSON - Operation: %s | Success: %s", 
                  timestamp.c_str(), operation.c_str(), success ? "YES" : "NO");
    if (!success && error.length() > 0) {
        Serial.printf(" | Error: %s", error.c_str());
    }
    Serial.println();
}

void logMemoryOperation(const String& operation, size_t bytes, bool success) {
    String timestamp = String(millis());
    Serial.printf("💾 %s MEMORY - Operation: %s | Bytes: %d | Success: %s", 
                  timestamp.c_str(), operation.c_str(), bytes, success ? "YES" : "NO");
    Serial.println();
}

void logTiming(const String& operation, unsigned long startTime, unsigned long endTime) {
    String timestamp = String(millis());
    unsigned long duration = endTime - startTime;
    Serial.printf("⏱️ %s TIMING - Operation: %s | Duration: %lu ms", 
                  timestamp.c_str(), operation.c_str(), duration);
    Serial.println();
}

// ========================================
// 📋 FLOW STATE MANAGEMENT
// ========================================

void updateAudioFlowState(const String& newState) {
    if (currentAudioFlowState != newState) {
        logAudioFlowState(newState, "State changed from " + currentAudioFlowState);
        currentAudioFlowState = newState;
    }
}

void updateWebSocketFlowState(const String& newState) {
    if (currentWebSocketFlowState != newState) {
        logWebSocketFlowState(newState, "State changed from " + currentWebSocketFlowState);
        currentWebSocketFlowState = newState;
    }
}

void updateAuthFlowState(const String& newState) {
    if (currentAuthFlowState != newState) {
        logAuthFlowState(newState, "State changed from " + currentAuthFlowState);
        currentAuthFlowState = newState;
    }
}

void updateSystemState(const String& newState) {
    if (currentSystemState != newState) {
        logSystemEvent("State changed", currentSystemState + " -> " + newState);
        currentSystemState = newState;
    }
}

void logCurrentFlowStates() {
    String timestamp = String(millis());
    Serial.printf("📋 %s CURRENT FLOW STATES:", timestamp.c_str());
    Serial.println();
    Serial.printf("   🎵 Audio: %s", currentAudioFlowState.c_str());
    Serial.println();
    Serial.printf("   🌐 WebSocket: %s", currentWebSocketFlowState.c_str());
    Serial.println();
    Serial.printf("   🔐 Auth: %s", currentAuthFlowState.c_str());
    Serial.println();
    Serial.printf("   💻 System: %s", currentSystemState.c_str());
    Serial.println();
}
