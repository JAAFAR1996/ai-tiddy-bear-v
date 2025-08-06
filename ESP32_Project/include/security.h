#ifndef SECURITY_H
#define SECURITY_H

#include <Arduino.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <mbedtls/sha256.h>

// Security configuration
struct SecurityConfig {
  String device_certificate;
  String private_key;
  String ca_certificate;
  String api_token;
  String device_signature;
  unsigned long token_expires;
  bool ssl_enabled;
  bool certificate_validation;
};

// Authentication status
enum AuthStatus {
  AUTH_NONE,
  AUTH_PENDING,
  AUTH_SUCCESS,
  AUTH_FAILED,
  AUTH_EXPIRED
};

// Security functions
bool initSecurity();
bool authenticateDevice();
bool validateServerCertificate();
bool renewAuthToken();
bool isAuthenticated();
AuthStatus getAuthStatus();
String generateDeviceSignature();
String encryptData(const String& data);
String decryptData(const String& encryptedData);
bool validateDataIntegrity(const String& data, const String& signature);
void handleSecurityError(const String& error);
void rotateSecrets();
bool secureWebSocketConnect();

// WebSocket token management
bool saveAuthTokenToFile(const String& token);
String loadAuthTokenFromFile();
bool updateWebSocketToken();

// Certificate management
bool loadCertificates();
bool storeCertificates();
bool updateCertificates();
bool validateCertificateChain();

// Secure communication
WiFiClientSecure* createSecureClient();
bool sendSecureRequest(const String& url, const String& payload, String& response);
bool verifyServerResponse(const String& response, const String& signature);

// Security monitoring
void checkSecurityHealth();
void logSecurityEvent(const String& event, int severity);
bool detectSecurityThreats();

// Constants
extern const char* ROOT_CA_CERT;
extern const int MAX_AUTH_RETRIES;
extern const unsigned long AUTH_TOKEN_LIFETIME;
extern const unsigned long SECURITY_CHECK_INTERVAL;

// Global variables
extern SecurityConfig securityConfig;
extern AuthStatus currentAuthStatus;
extern unsigned long lastSecurityCheck;
extern int authRetryCount;

#endif // SECURITY_H
