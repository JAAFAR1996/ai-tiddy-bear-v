#ifndef TLS_CERTIFICATE_MANAGER_H
#define TLS_CERTIFICATE_MANAGER_H

#include "config.h"
#include "security.h"
#include <Arduino.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <mbedtls/x509_crt.h>
#include <mbedtls/pk.h>
#include <mbedtls/entropy.h>
#include <mbedtls/ctr_drbg.h>
#include <mbedtls/ssl.h>
#include <mbedtls/net_sockets.h>
#include <mbedtls/error.h>
#include <time.h>

// Certificate storage keys in NVS
#define NVS_NAMESPACE_CERTS     "certificates"
#define NVS_KEY_ROOT_CA         "root_ca"
#define NVS_KEY_DEVICE_CERT     "device_cert"
#define NVS_KEY_PRIVATE_KEY     "private_key"
#define NVS_KEY_CERT_BUNDLE     "cert_bundle"
#define NVS_KEY_PINNED_CERTS    "pinned_certs"
#define NVS_KEY_CERT_METADATA   "cert_meta"
#define NVS_KEY_LAST_RENEWAL    "last_renewal"
#define NVS_KEY_CERT_VERSION    "cert_version"

// Certificate validation constants
#define CERT_VALIDATION_BUFFER_SIZE   8192
#define MAX_CERT_CHAIN_LENGTH        10
#define CERT_RENEWAL_BUFFER_DAYS     30     // Renew 30 days before expiry
#define CERT_CHECK_INTERVAL_MS       3600000 // Check every hour
#define CERT_EMERGENCY_RENEWAL_DAYS  7      // Emergency renewal threshold
#define MAX_PINNED_CERTIFICATES      5      // Maximum pinned certificates
#define CERT_VALIDATION_TIMEOUT_MS   30000  // 30 second timeout

// Certificate status codes
enum CertificateStatus {
    CERT_STATUS_UNKNOWN,
    CERT_STATUS_VALID,
    CERT_STATUS_EXPIRED,
    CERT_STATUS_EXPIRING_SOON,
    CERT_STATUS_INVALID_CHAIN,
    CERT_STATUS_REVOKED,
    CERT_STATUS_NOT_TRUSTED,
    CERT_STATUS_ERROR
};

// SSL/TLS security levels
enum SecurityLevel {
    SECURITY_LEVEL_MINIMAL,    // Basic TLS with minimal validation
    SECURITY_LEVEL_STANDARD,   // Standard TLS with certificate validation
    SECURITY_LEVEL_HIGH,       // High security with certificate pinning
    SECURITY_LEVEL_MAXIMUM     // Maximum security with all validations
};

// Certificate types
enum CertificateType {
    CERT_TYPE_ROOT_CA,
    CERT_TYPE_INTERMEDIATE_CA,
    CERT_TYPE_DEVICE_CLIENT,
    CERT_TYPE_SERVER,
    CERT_TYPE_PINNED,
    CERT_TYPE_INTERMEDIATE = CERT_TYPE_INTERMEDIATE_CA  // Alias for compatibility
};

// Certificate information structure
struct CertificateInfo {
    String subject;
    String issuer;
    String serialNumber;
    String fingerprint;
    time_t notBefore;        // Certificate valid from time
    time_t notAfter;         // Certificate valid until time
    int keyLength;
    String signatureAlgorithm;
    bool isValid;
    bool isCA;
    bool isSelfSigned;
    CertificateStatus status;
};

// Certificate validation result
struct CertificateValidationResult {
    bool isValid;
    CertificateStatus status;
    String errorMessage;
    int errorCode;
    float trustScore;
    bool chainComplete;
    int chainLength;
    int daysUntilExpiry;
    time_t expiryDate;
    String validationDetails;
};

// Certificate renewal configuration
struct RenewalConfig {
    bool autoRenewalEnabled;
    uint32_t renewalThresholdDays;
    String renewalEndpoint;
    String renewalToken;
    uint32_t maxRetryAttempts;
    uint32_t retryIntervalMs;
    bool emergencyRenewalEnabled;
};

// Certificate pinning configuration
struct PinningConfig {
    bool enabled;
    String pinnedFingerprints[MAX_PINNED_CERTIFICATES];
    uint8_t pinnedCount;
    bool allowBackupPins;
    bool strictPinning;
    uint32_t pinValidityDays;
};

// TLS Certificate Manager class
class TLSCertificateManager {
public:
    // Constructor and initialization
    TLSCertificateManager();
    ~TLSCertificateManager();
    
    // Core initialization and management
    bool init();
    bool initSecureNVS();
    void cleanup();
    
    // Certificate loading and storage
    bool loadCertificates();
    bool loadCertificateFromNVS(const String& key, String& certificate);
    bool storeCertificateInNVS(const String& key, const String& certificate);
    bool clearCertificateFromNVS(const String& key);
    
    // Certificate validation
    bool validateCertificate(const String& cert);
    CertificateValidationResult validateCertificateDetailed(const String& cert, CertificateType type = CERT_TYPE_SERVER);
    bool validateCertificateChain();
    bool validateCertificateChain(const String& deviceCert, const String& caCert);
    bool validateAgainstPinnedCerts(const String& fingerprint);
    
    // Certificate information extraction
    CertificateInfo extractCertificateInfo(const String& cert);
    String extractCertificateFingerprint(const String& cert);
    time_t extractCertificateExpiry(const String& cert);
    bool isCertificateExpired(const String& cert);
    bool isCertificateExpiringSoon(const String& cert, uint32_t thresholdDays = CERT_RENEWAL_BUFFER_DAYS);
    
    // SSL/TLS configuration
    bool enableSSL();
    void disableSSL();
    bool isSSLEnabled() const;
    bool configureSecureClient(WiFiClientSecure* client);
    bool setSecurityLevel(SecurityLevel level);
    SecurityLevel getSecurityLevel() const;
    
    // Certificate getters
    String getRootCA();
    String getDeviceCert();
    String getPrivateKey();
    String getCertificateBundle();
    
    // Certificate setters with validation
    bool setRootCA(const String& rootCA);
    bool setDeviceCert(const String& deviceCert);
    bool setPrivateKey(const String& privateKey);
    bool setCertificateBundle(const String& bundle);
    
    // Certificate renewal
    bool checkCertificateExpiry();
    bool renewCertificates();
    bool renewCertificate(CertificateType type);
    bool scheduleRenewal(uint32_t delayMs = 0);
    void setRenewalConfig(const RenewalConfig& config);
    RenewalConfig getRenewalConfig() const;
    
    // Certificate pinning
    bool enableCertificatePinning();
    void disableCertificatePinning();
    bool addPinnedCertificate(const String& fingerprint);
    bool removePinnedCertificate(const String& fingerprint);
    void clearPinnedCertificates();
    bool isPinningEnabled() const;
    void setPinningConfig(const PinningConfig& config);
    PinningConfig getPinningConfig() const;
    
    // Certificate backup and restore
    bool createCertificateBackup();
    bool restoreCertificateBackup(const String& backupId = "");
    bool exportCertificates(JsonObject& exportData);
    bool importCertificates(const JsonObject& importData);
    
    // Production security features
    bool enableProductionSecurity();
    bool validateProductionCertificates();
    bool enforceStrictValidation();
    bool setupAutomaticRenewal();
    
    // Monitoring and diagnostics
    void performCertificateHealthCheck();
    void printCertificateStatus();
    void printCertificateInfo(const String& cert);
    JsonObject getCertificateMetrics();
    bool runCertificateDiagnostics();
    
    // Error handling and recovery
    void handleCertificateError(const String& error, int errorCode);
    bool recoverFromCertificateFailure();
    void setFallbackMode(bool enabled);
    bool isFallbackMode() const;
    
    // Security monitoring integration
    void enableSecurityMonitoring();
    void reportSecurityEvent(const String& event, int severity);
    bool detectCertificateTampering();
    
    // Static utility functions
    static String generateCertificateFingerprint(const String& cert);
    static bool compareCertificateFingerprints(const String& fp1, const String& fp2);
    static time_t parseCertificateDate(const String& dateStr);
    static String formatCertificateDate(time_t timestamp);
    static bool isValidCertificateFormat(const String& cert);
    
private:
    // Internal state management
    void initializeState();
    void resetState();
    void updateCertificateMetadata();
    
    // Internal validation helpers
    bool validatePEMFormat(const String& cert);
    bool validateCertificateStructure(const String& cert);
    bool validateKeyPairMatch(const String& cert, const String& privateKey);
    mbedtls_x509_crt* parseCertificate(const String& cert);
    mbedtls_pk_context* parsePrivateKey(const String& key);
    float calculateTrustScore(const CertificateInfo& certInfo, CertificateType type);
    String generateValidationReport(const CertificateInfo& certInfo, const CertificateValidationResult& result);
    
    // Internal storage helpers
    bool storeCertificateSecurely(const String& key, const String& cert, bool encrypted = false);
    String loadCertificateSecurely(const String& key, bool encrypted = false);
    bool verifyCertificateIntegrity(const String& key, const String& cert);
    String calculateCertificateChecksum(const String& cert);
    
    // Internal renewal helpers
    bool downloadCertificateFromServer(const String& endpoint, String& certificate);
    bool validateRenewalResponse(const String& response);
    void scheduleNextRenewalCheck();
    bool isRenewalDue(CertificateType type);
    
    // Internal security helpers
    bool initializeMbedTLS();
    void cleanupMbedTLS();
    int validateCertificateChainMbedTLS(mbedtls_x509_crt* cert, mbedtls_x509_crt* ca);
    bool verifyMbedTLSOperation(int result, const String& operation);
    
    // Internal error handling
    void logError(const String& operation, int errorCode);
    void logWarning(const String& message);
    void logInfo(const String& message);
    String mbedTLSErrorToString(int errorCode);

private:
    // Core state
    bool initialized;
    bool sslEnabled;
    SecurityLevel currentSecurityLevel;
    bool fallbackMode;
    
    // NVS storage
    Preferences nvs;
    bool nvsInitialized;
    
    // Certificate storage
    String rootCACert;
    String deviceCertificate;
    String devicePrivateKey;
    String certificateBundle;
    
    // Configuration
    RenewalConfig renewalConfig;
    PinningConfig pinningConfig;
    bool strictValidationEnabled;
    bool productionModeEnabled;
    
    // Monitoring and metrics
    uint32_t certificateCheckCount;
    uint32_t successfulValidations;
    uint32_t failedValidations;
    uint32_t renewalAttempts;
    uint32_t successfulRenewals;
    unsigned long lastCertificateCheck;
    unsigned long lastRenewalAttempt;
    
    // mbedTLS contexts
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context ctr_drbg;
    mbedtls_x509_crt cacert;
    mbedtls_x509_crt clicert;
    mbedtls_pk_context pkey;
    bool mbedTLSInitialized;
    
    // Error tracking
    String lastError;
    int lastErrorCode;
    uint32_t errorCount;
    unsigned long lastErrorTime;
    
    // Certificate metadata
    CertificateInfo rootCAInfo;
    CertificateInfo deviceCertInfo;
    time_t certificateLoadTime;
    String certificateVersion;
    
    // Security monitoring
    bool securityMonitoringEnabled;
    uint32_t securityEventCount;
    uint32_t tamperingDetectionCount;
    
    // Task management
    TaskHandle_t renewalTaskHandle;
    TaskHandle_t monitoringTaskHandle;
    SemaphoreHandle_t certificateMutex;
};

// Global instance declaration
extern TLSCertificateManager tlsCertManager;

// C-style wrapper functions for integration
extern "C" {
    bool initTLSCertificateManager();
    bool loadTLSCertificates();
    bool validateTLSCertificate(const char* cert);
    bool enableTLSSSL();
    void disableTLSSSL();
    bool isTLSSSLEnabled();
    const char* getTLSRootCA();
    const char* getTLSDeviceCert();
    const char* getTLSPrivateKey();
    void performTLSCertificateHealthCheck();
    void cleanupTLSCertificateManager();
}

// Configuration integration callbacks
void onCertificateRenewalComplete(bool success);
void onCertificateValidationFailed(const String& error);
void onSecurityLevelChanged(SecurityLevel newLevel);

// Constants and default configurations
extern const char* DEFAULT_ROOT_CA_BUNDLE;
extern const RenewalConfig DEFAULT_RENEWAL_CONFIG;
extern const PinningConfig DEFAULT_PINNING_CONFIG;

// Known trusted root CAs for fallback
extern const char* TRUSTED_ROOT_CAS[];
extern const int TRUSTED_ROOT_CAS_COUNT;

#endif // TLS_CERTIFICATE_MANAGER_H