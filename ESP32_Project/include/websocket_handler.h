#ifndef WEBSOCKET_HANDLER_H
#define WEBSOCKET_HANDLER_H

#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "config.h"

extern WebSocketsClient webSocket;
extern bool isConnected;

// WebSocket functions
void initWebSocket();
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length);
void handleIncomingMessage(String message);
void reconnectWebSocket();
void connectWebSocket();

// Message sending functions
void sendHandshake();
void sendSensorData();
void sendHeartbeat();
void sendButtonEvent();
void sendResponse(String status, String message, String requestId = "");
void sendDeviceStatus();
void sendAudioData(uint8_t* audioData, size_t length);
// Audio session helpers
void sendAudioStartSession();
void sendAudioEndSession();
void markNextChunkFinal();

// Command handlers
void handleLEDCommand(JsonObject params);
void handleAudioCommand(JsonObject params);
void handleAnimationCommand(JsonObject params);
void handleStatusRequest();
void handleAudioResponse(JsonObject params);

// Utility functions
String createMessage(String type, JsonObject data = JsonObject());
void logMessage(String direction, String message);

// Network performance optimization
size_t getOptimalChunkSize();
void adjustChunkSizeDown();
void adjustChunkSizeUp();
void printNetworkStats();

// Connection health monitoring
void updateConnectionQuality();
void sendPingFrame();
void performConnectionHealthCheck();
void getConnectionHealth(JsonObject& healthObj);

// Connection event handlers
void onWebSocketConnected();
void onWebSocketDisconnected();
void onWebSocketError();
void onWebSocketMessageReceived();
void scheduleReconnection();
void scheduleReconnection(unsigned long delayMs);

// Enhanced connection management
void handleWebSocketLoop();
void sendConnectionHealthReport();
bool isConnectionHealthy();
void resetConnectionStats();

// New server protocol handlers
void handleWelcomeMessage(DynamicJsonDocument& doc);
void handlePolicyUpdate(DynamicJsonDocument& doc);
void handleSecurityAlert(DynamicJsonDocument& doc);
void handleAuthenticationResponse(DynamicJsonDocument& doc, bool success);
void handleIncomingAudioFrame(uint8_t* audioData, size_t length);
bool handleJWTRefreshMessage(const String& refreshMessage);

#endif
