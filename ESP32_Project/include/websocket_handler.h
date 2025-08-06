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

// Message sending functions
void sendHandshake();
void sendSensorData();
void sendButtonEvent();
void sendHeartbeat();
void sendResponse(String status, String message, String requestId = "");
void sendDeviceStatus();
void sendAudioData(uint8_t* audioData, size_t length);

// Command handlers
void handleLEDCommand(JsonObject params);
void handleServoCommand(JsonObject params);
void handleAudioCommand(JsonObject params);
void handleAnimationCommand(JsonObject params);
void handleStatusRequest();
void handleAudioResponse(JsonObject params);

// Utility functions
String createMessage(String type, JsonObject data = JsonObject());
void logMessage(String direction, String message);

#endif