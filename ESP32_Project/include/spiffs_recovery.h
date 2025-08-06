#ifndef SPIFFS_RECOVERY_H
#define SPIFFS_RECOVERY_H

#include <Arduino.h>
#include <SPIFFS.h>
#include <FS.h>
#include <Preferences.h>

// SPIFFS Recovery System
// Handles filesystem corruption, power failures, and data recovery

enum SPIFFSStatus {
  SPIFFS_OK = 0,
  SPIFFS_CORRUPTED = 1,
  SPIFFS_FULL = 2,
  SPIFFS_MOUNT_FAILED = 3,
  SPIFFS_WRITE_FAILED = 4,
  SPIFFS_READ_FAILED = 5,
  SPIFFS_CRITICAL_ERROR = 6
};

enum RecoveryAction {
  RECOVERY_NONE = 0,
  RECOVERY_REMOUNT = 1,
  RECOVERY_FORMAT = 2,
  RECOVERY_BACKUP_RESTORE = 3,
  RECOVERY_FACTORY_RESET = 4
};

struct SPIFFSHealth {
  SPIFFSStatus status;
  size_t totalBytes;
  size_t usedBytes;
  size_t freeBytes;
  int fileCount;
  bool canWrite;
  bool canRead;
  unsigned long lastCheck;
  int errorCount;
  int recoveryCount;
};

class SPIFFSRecovery {
private:
  static SPIFFSHealth health;
  static Preferences recoveryPrefs;
  static bool emergencyMode;
  static String backupPath;
  static unsigned long lastHealthCheck;
  static const unsigned long HEALTH_CHECK_INTERVAL;
  
  static bool performFileSystemCheck();
  static bool attemptRemount();
  static bool attemptFormat();
  static bool createBackup();
  static bool restoreFromBackup();
  static void logRecoveryAction(RecoveryAction action, bool success);
  static void enableEmergencyMode();
  static void disableEmergencyMode();

public:
  // Initialize recovery system
  static bool init();
  
  // Health monitoring
  static SPIFFSHealth checkHealth();
  static bool isHealthy();
  static void periodicHealthCheck();
  
  // Safe file operations with automatic recovery
  static File safeOpen(const String& path, const char* mode);
  static bool safeWrite(const String& path, const String& data);
  static String safeRead(const String& path);
  static bool safeDelete(const String& path);
  static bool safeExists(const String& path);
  
  // Transaction-safe operations (atomic writes)
  static bool atomicWrite(const String& path, const String& data);
  static bool atomicUpdate(const String& path, const String& newData);
  
  // Recovery operations
  static RecoveryAction diagnoseAndRecover();
  static bool performRecovery(RecoveryAction action);
  static bool validateFileSystem();
  
  // Critical file protection
  static bool protectCriticalFiles();
  static bool backupCriticalFiles();
  static bool restoreCriticalFiles();
  
  // Emergency operations (when SPIFFS is completely broken)
  static bool isEmergencyMode();
  static void handleEmergencyStorage();
  
  // Statistics and debugging
  static SPIFFSHealth getHealthStatus();
  static void printHealthReport();
  static void resetRecoveryCounters();
  
  // Power failure recovery
  static bool recoverFromPowerFailure();
  static bool checkForIncompleteOperations();
  static void markOperationStart(const String& operation);
  static void markOperationComplete(const String& operation);
};

// Safe macros for SPIFFS operations
#define SAFE_SPIFFS_OPEN(path, mode) SPIFFSRecovery::safeOpen(path, mode)
#define SAFE_SPIFFS_WRITE(path, data) SPIFFSRecovery::safeWrite(path, data)
#define SAFE_SPIFFS_READ(path) SPIFFSRecovery::safeRead(path)
#define SAFE_SPIFFS_EXISTS(path) SPIFFSRecovery::safeExists(path)
#define ATOMIC_SPIFFS_WRITE(path, data) SPIFFSRecovery::atomicWrite(path, data)

// Critical files that should be backed up
extern const char* CRITICAL_FILES[];
extern const int CRITICAL_FILES_COUNT;

#endif