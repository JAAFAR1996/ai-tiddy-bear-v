#include "wifi_manager.h"
#include "wifi_portal.h"
#include "hardware.h"
#include "time_sync.h"
#include <WiFi.h>
#include <Preferences.h>
#include <HTTPClient.h>
#include <esp_task_wdt.h>
#include <algorithm>

// Forward declarations
bool connectToWiFi();
void attemptWiFiReconnectionStep();
bool reconnectWiFi();
void handleInternetDisconnection();
String getWiFiReconnectStats();
bool isWiFiStable();

// 🧸 PRODUCTION WIFI MANAGER - Audio-only teddy bear
// Auto-reconnect with exponential backoff for 2-hour stability test
// FOCUS: Robust connection with automatic recovery, fully non-blocking

// WiFi state and reconnection management
static bool wifiInitialized = false;
static Preferences prefs;
bool isConnectedToInternet = false;
unsigned long lastInternetCheck = 0;

// Reconnection state
struct WiFiReconnectState {
  unsigned long lastDisconnectTime = 0;
  unsigned long reconnectDelay = 500;        // Start with 0.5s
  unsigned long maxReconnectDelay = 8000;    // Max 8s as required
  unsigned int reconnectAttempts = 0;
  unsigned long totalDisconnections = 0;
  bool isReconnecting = false;
  unsigned long lastConnectionCheck = 0;
  bool wasConnected = false;
};

static WiFiReconnectState reconnectState;

// Non-blocking reconnection check state
struct {
  bool inProgress = false;
  unsigned long startCheckMs = 0;
} quickCheck;

// Production WiFi initialization
bool initWiFiManager() {
  if (wifiInitialized) return true;
  
  Serial.println("📶 Production WiFi init for teddy bear");
  
  // Unified WiFi setup for production stability
  WiFi.persistent(false);        // Don't save to flash every time
  WiFi.mode(WIFI_STA);           // Station mode only
  // Minimize inrush during RF init: start with low TX power + modem sleep
  WiFi.setTxPower(WIFI_POWER_8_5dBm);
  WiFi.setSleep(true);           // Enable modem sleep during early boot to reduce peaks
  WiFi.setAutoReconnect(false);  // We handle reconnection manually
  delay(150);                    // Small settle time for regulator
  
  wifiInitialized = true;
  return true;
}

// Simple WiFi connection (ONE ATTEMPT ONLY)
bool connectToWiFi() {
  if (!wifiInitialized) initWiFiManager();

  // Load credentials from NVS
  prefs.begin("wifi", true);
  String ssid = prefs.getString("ssid", "");
  String password = prefs.getString("password", "");
  prefs.end();

  if (ssid.isEmpty()) {
    Serial.println("❌ No stored WiFi credentials — skipping STA connect");
    return false; // main.cpp سيبدأ البوابة عند الفشل
  }

  Serial.printf("📶 Connecting to WiFi: %s\n", ssid.c_str());
  WiFi.begin(ssid.c_str(), password.c_str());

  // Non-blocking: return status immediately, manager will handle retries
  unsigned long start = millis();
  while (millis() - start < 2000 && WiFi.status() != WL_CONNECTED) {
    delay(50);
    esp_task_wdt_reset();
    yield();
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("✅ WiFi connected: %s\n", WiFi.localIP().toString().c_str());
    
    // Reset reconnection state on successful connection
    reconnectState.reconnectAttempts = 0;
    reconnectState.reconnectDelay = 500;
    reconnectState.isReconnecting = false;
    
    // Non-blocking LED indicator
    setLEDColor("green", 100);
    
    // Restore runtime settings after successful association
    WiFi.setSleep(false);               // Reduce latency for audio
    WiFi.setTxPower(WIFI_POWER_11dBm);  // Bump TX power modestly once stable
    
    // Optionally restore CPU frequency (if reduced during boot)
    setCpuFrequencyMhz(160);            // Balanced performance/power
    
    // Sync time after successful connection
    Serial.println("⏰ Syncing time after WiFi connection");
    syncTimeWithNTP();
    
    return true;
  } else {
    Serial.println("❌ WiFi not connected yet — caller may start setup portal");
    setLEDColor("red", 100);
    return false;
  }
}

// Production WiFi manager with fully non-blocking auto-reconnect
void handleWiFiManager() {
  unsigned long now = millis();
  bool currentlyConnected = (WiFi.status() == WL_CONNECTED);
  
  // Check connection status every 5 seconds
  if (now - reconnectState.lastConnectionCheck > 5000) {
    reconnectState.lastConnectionCheck = now;
    
    if (!currentlyConnected && reconnectState.wasConnected) {
      // Just disconnected
      reconnectState.lastDisconnectTime = now;
      reconnectState.totalDisconnections++;
      reconnectState.reconnectDelay = 500; // Reset to 0.5s
      reconnectState.reconnectAttempts = 0;
      reconnectState.isReconnecting = true;
      quickCheck.inProgress = false; // Reset quick check state
      
      Serial.printf("❌ WiFi disconnected (total: %lu)\n", reconnectState.totalDisconnections);
      setLEDColor("orange", 100);
    }
    
    if (currentlyConnected && !reconnectState.wasConnected) {
      // Just reconnected - save attempt count before reset
      unsigned int attempts = reconnectState.reconnectAttempts;
      reconnectState.isReconnecting = false;
      reconnectState.reconnectAttempts = 0;
      reconnectState.reconnectDelay = 500;
      
      Serial.printf("✅ WiFi reconnected after %u attempts\n", attempts);
      setLEDColor("green", 100);
      
      // Sync time after reconnection
      Serial.println("⏰ Syncing time after WiFi reconnection");
      syncTimeWithNTP();
    }
    
    reconnectState.wasConnected = currentlyConnected;
  }
  
  // Handle automatic reconnection with non-blocking backoff
  if (!currentlyConnected && reconnectState.isReconnecting) {
    if (now - reconnectState.lastDisconnectTime >= reconnectState.reconnectDelay) {
      attemptWiFiReconnectionStep();
    }
  }

  // إذا ظل غير متصل لأكثر من 3 دقائق، فعّل بوابة الإعداد تلقائياً
  if (!currentlyConnected) {
    const unsigned long DISCONNECT_PORTAL_TIMEOUT = 180000; // 3 دقائق
    // لو لم يكن لدينا بوابة نشطة ومر الوقت الكافي منذ آخر فصل، شغّلها
    if (!isPortalActive() && reconnectState.lastDisconnectTime != 0 &&
        (now - reconnectState.lastDisconnectTime) > DISCONNECT_PORTAL_TIMEOUT) {
      Serial.println("⏳ WiFi offline for >3 minutes — starting WiFi setup portal");
      startWiFiPortal();
      // أوقف محاولات إعادة الاتصال أثناء البوابة
      reconnectState.isReconnecting = false;
    }
  }
}

// Manual WiFi reconnection (fully non-blocking)
bool reconnectWiFi() {
  Serial.println("🔄 Manual WiFi reconnect");
  WiFi.disconnect();
  
  // Make it non-blocking: reset state and let loop handle it
  reconnectState.reconnectAttempts = 0;
  reconnectState.reconnectDelay = 500;
  quickCheck.inProgress = false;
  reconnectState.isReconnecting = true;
  reconnectState.lastDisconnectTime = millis() - reconnectState.reconnectDelay; // Trigger immediate attempt
  
  return true;
}

// Non-blocking automatic WiFi reconnection step
void attemptWiFiReconnectionStep() {
  if (reconnectState.reconnectAttempts >= 10) {
    Serial.println("❌ Max reconnect attempts reached, waiting 60s");
    reconnectState.lastDisconnectTime = millis();
    reconnectState.reconnectDelay = 60000; // Wait 1 minute
    reconnectState.reconnectAttempts = 0;
    quickCheck.inProgress = false;
    return;
  }
  
  if (!quickCheck.inProgress) {
    // Start reconnection attempt
    reconnectState.reconnectAttempts++;
    Serial.printf("🔄 Auto-reconnect attempt %u (delay: %lums)\n", 
                  reconnectState.reconnectAttempts, reconnectState.reconnectDelay);
    
    // Load saved credentials
    prefs.begin("wifi", true);
    String ssid = prefs.getString("ssid", "");
    String password = prefs.getString("password", "");
    prefs.end();
    
    if (ssid.length() == 0) {
      Serial.println("❌ No WiFi credentials for auto-reconnect");
      reconnectState.isReconnecting = false;
      return;
    }
    
    // Start non-blocking connection attempt
    WiFi.disconnect();
    delay(100); // Minimal delay needed for disconnect
    WiFi.begin(ssid.c_str(), password.c_str());
    
    quickCheck.inProgress = true;
    quickCheck.startCheckMs = millis();
    return;
  }
  
  // Check connection progress (non-blocking)
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("✅ Auto-reconnect successful");
    reconnectState.isReconnecting = false;
    reconnectState.reconnectAttempts = 0;
    reconnectState.reconnectDelay = 500; // Reset delay
    quickCheck.inProgress = false;
    return;
  }
  
  // Check if timeout reached (5 seconds window)
  if (millis() - quickCheck.startCheckMs >= 5000) {
    Serial.println("❌ Auto-reconnect failed");
    
    // Exponential backoff: 0.5s → 1s → 2s → 4s → 8s (using manual calculation)
    reconnectState.reconnectDelay = (reconnectState.reconnectDelay < reconnectState.maxReconnectDelay)
      ? reconnectState.reconnectDelay * 2 : reconnectState.maxReconnectDelay;
    
    reconnectState.lastDisconnectTime = millis();
    quickCheck.inProgress = false;
    
    Serial.printf("⏳ Next attempt in %lums\n", reconnectState.reconnectDelay);
  }
}

// Handle internet disconnection with non-blocking LED indication
void handleInternetDisconnection() {
  if (WiFi.status() != WL_CONNECTED) {
    static unsigned long lastBlink = 0;
    static bool ledOn = false;
    
    if (millis() - lastBlink > 2000) {
      if (ledOn) {
        clearLEDs();
        ledOn = false;
      } else {
        setLEDColor("red", 30);
        ledOn = true;
      }
      lastBlink = millis();
    }
  }
}

// Simple Internet connectivity test using HTTP 204 endpoint
bool testInternetConnection() {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  // Use HTTP (not HTTPS) to avoid certificate/time issues during basic connectivity check
  if (!http.begin("http://clients3.google.com/generate_204")) {
    return false;
  }
  int code = http.GET();
  http.end();
  return (code > 0 && code < 400);
}

// Get WiFi reconnection statistics for diagnostics
String getWiFiReconnectStats() {
  String stats = "WiFi Stats - Disconnections: " + String(reconnectState.totalDisconnections);
  stats += ", Attempts: " + String(reconnectState.reconnectAttempts);
  stats += ", Current delay: " + String(reconnectState.reconnectDelay) + "ms";
  stats += ", Reconnecting: " + String(reconnectState.isReconnecting ? "Yes" : "No");
  stats += ", Connected: " + String((WiFi.status() == WL_CONNECTED) ? "Yes" : "No");
  return stats;
}

// Check if WiFi is stable (connected for at least 30 seconds)
bool isWiFiStable() {
  return (WiFi.status() == WL_CONNECTED) && 
         !reconnectState.isReconnecting && 
         (millis() - reconnectState.lastDisconnectTime > 30000);
}

// Cleanup with state reset
void cleanupWiFiManager() {
  WiFi.disconnect();
  wifiInitialized = false;
  
  // Reset all reconnection state
  reconnectState = {};
  quickCheck.inProgress = false;
  
  Serial.println("🧹 WiFi cleanup for teddy bear");
}
