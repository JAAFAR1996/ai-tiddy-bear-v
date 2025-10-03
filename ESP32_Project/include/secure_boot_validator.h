#ifndef SECURE_BOOT_VALIDATOR_H
#define SECURE_BOOT_VALIDATOR_H

#include <Arduino.h>

// Secure boot validation functions
bool initSecureBootValidator();
bool performBootValidation();
void cleanupSecureBootValidator();

// Individual validation components
bool verifyFirmwareIntegrity();
bool verifyFirmwareSignature();
bool performAdditionalSecurityChecks();

// Security checks
bool verifyPartitionTable();
bool verifyBootloaderIntegrity();
bool checkDebugInterfaces();
bool verifySecureConfiguration();

// Failure handling
void handleBootValidationFailure();
void resetBootFailureCounter();

// Status functions
bool isBootValidated();
bool isSecureBootEnabled();
void printBootSecurityStats();

#endif