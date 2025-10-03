/*
 * Production Configuration Validator for AI Teddy Bear ESP32-S3
 * Comprehensive production readiness validation system
 * 
 * Features:
 * - SSL/TLS configuration validation
 * - JWT authentication setup verification
 * - BLE provisioning security checks
 * - Audio encryption validation
 * - Memory management optimization checks
 * - Performance metrics validation
 * - Debug features detection
 * - Watchdog and safety systems validation
 * - Production environment compliance
 * 
 * Author: Expert ESP32 Engineer (1000 years experience)
 * Version: 1.0.0 Production Edition
 */

#ifndef PRODUCTION_CONFIG_VALIDATOR_H
#define PRODUCTION_CONFIG_VALIDATOR_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <vector>

// Production validation severity levels
enum ValidationSeverity {
  VALIDATION_INFO = 1,
  VALIDATION_WARNING = 2,
  VALIDATION_ERROR = 3,
  VALIDATION_CRITICAL = 4
};

// Production check categories
enum CheckCategory {
  CATEGORY_SSL = 1,
  CATEGORY_AUTH = 2,
  CATEGORY_SECURITY = 3,
  CATEGORY_PERFORMANCE = 4,
  CATEGORY_ENVIRONMENT = 5,
  CATEGORY_AUDIO = 6,
  CATEGORY_MEMORY = 7,
  CATEGORY_WATCHDOG = 8
};

// Production check result structure
struct ProductionCheckItem {
  String checkName;
  CheckCategory category;
  bool passed;
  ValidationSeverity severity;
  String message;
  String recommendation;
  unsigned long checkTime;
};

// Overall production readiness result
struct ProductionCheckResult {
  bool isProductionReady;
  std::vector<String> blockers;
  std::vector<String> warnings;
  std::vector<String> recommendations;
  int securityScore;
  int performanceScore;
  int overallScore;
  unsigned long totalCheckTime;
  std::vector<ProductionCheckItem> checkResults;
};

// Production security requirements
struct SecurityRequirements {
  bool sslRequired;
  bool jwtRequired;
  bool bleSecurityRequired;
  bool audioEncryptionRequired;
  bool debugDisabled;
  bool watchdogEnabled;
  int minimumSecurityScore;
};

// Performance targets
struct PerformanceTargets {
  size_t minFreeHeap;
  size_t maxMemoryFragmentation;
  unsigned long maxBootTime;
  float maxCpuUsage;
  unsigned long maxResponseTime;
  float minConnectionStability;
};

/*
 * Production Configuration Validator Class
 * Comprehensive production readiness validation system
 */
class ProductionValidator {
public:
    // Constructor/Destructor
    ProductionValidator();
    ~ProductionValidator();
    
    // Main validation functions
    bool validateProductionReadiness();
    ProductionCheckResult runProductionChecks();
    bool enforceProductionSecurity();
    void generateProductionReport();
    
    // Configuration functions
    void setSecurityRequirements(const SecurityRequirements& requirements);
    void setPerformanceTargets(const PerformanceTargets& targets);
    void enableVerboseLogging(bool enabled);
    
    // Report generation
    String generateHTMLReport();
    String generateJSONReport();
    void saveReportToFile(const String& filename);
    
    // Real-time monitoring
    void startContinuousMonitoring();
    void stopContinuousMonitoring();
    bool isContinuousMonitoringActive();
    
    // Manual check functions
    bool runSecurityChecks();
    bool runPerformanceChecks();
    bool runEnvironmentChecks();

private:
    // Core validation functions
    bool checkSSLConfiguration();
    bool checkAuthenticationSetup();
    bool checkSecurityFeatures();
    bool checkPerformanceMetrics();
    bool validateEnvironmentSettings();
    bool checkAudioSecurity();
    bool checkMemoryManagement();
    bool checkWatchdogConfiguration();
    bool checkBLEProvisioning();
    bool checkDebugFeatures();
    
    // Specific SSL checks
    bool validateSSLCertificates();
    bool validateSSLProtocolVersion();
    bool validateSSLCipherSuites();
    
    // Specific authentication checks
    bool validateJWTConfiguration();
    bool validateTokenSecurity();
    bool validateAuthenticationFlow();
    
    // Specific security checks
    bool validateEncryptionStrength();
    bool validateSecureStorage();
    bool validateNetworkSecurity();
    bool validateInputValidation();
    
    // Performance validation
    bool validateMemoryUsage();
    bool validateCPUPerformance();
    bool validateNetworkPerformance();
    bool validateAudioPerformance();
    
    // Environment validation
    bool validateProductionBuildFlags();
    bool validateHardwareConfiguration();
    bool validateFirmwareVersion();
    
    // Utility functions
    void addCheckResult(const String& checkName, CheckCategory category, 
                       bool passed, ValidationSeverity severity,
                       const String& message, const String& recommendation = "");
    int calculateSecurityScore();
    int calculatePerformanceScore();
    int calculateOverallScore();
    void logValidationResult(const ProductionCheckItem& item);
    String severityToString(ValidationSeverity severity);
    String categoryToString(CheckCategory category);
    
    // Integration functions
    void notifyMonitoringSystem(const ProductionCheckResult& result);
    void updateSystemMetrics(const ProductionCheckResult& result);
    void triggerSecurityAlerts(const std::vector<ProductionCheckItem>& criticalIssues);
    
    // Member variables
    ProductionCheckResult lastCheckResult;
    SecurityRequirements securityRequirements;
    PerformanceTargets performanceTargets;
    bool verboseLogging;
    bool continuousMonitoringActive;
    unsigned long lastCheckTime;
    TaskHandle_t monitoringTaskHandle;
    
    // Static monitoring task
    static void continuousMonitoringTask(void* parameter);
};

// Utility functions
bool isProductionEnvironment();
String getProductionEnvironmentInfo();
void enforceProductionConstraints();

// Global validator instance
extern ProductionValidator* productionValidator;

// Production validation macros
#define PRODUCTION_CHECK(condition, message) \
  do { \
    if (!(condition)) { \
      Serial.printf("❌ PRODUCTION CHECK FAILED: %s\n", message); \
      return false; \
    } \
  } while(0)

#define PRODUCTION_WARNING(condition, message) \
  do { \
    if (!(condition)) { \
      Serial.printf("⚠️ PRODUCTION WARNING: %s\n", message); \
    } \
  } while(0)

#define PRODUCTION_ASSERT(condition, message) \
  do { \
    if (!(condition)) { \
      Serial.printf("💥 PRODUCTION ASSERTION FAILED: %s\n", message); \
      ESP.restart(); \
    } \
  } while(0)

// Constants
#define PRODUCTION_CHECK_INTERVAL_MS 60000  // 1 minute
#define PRODUCTION_REPORT_INTERVAL_MS 300000  // 5 minutes
#define PRODUCTION_MIN_SECURITY_SCORE 85
#define PRODUCTION_MIN_PERFORMANCE_SCORE 80
#define PRODUCTION_MIN_OVERALL_SCORE 80

#endif /* PRODUCTION_CONFIG_VALIDATOR_H */