#include "spiffs_recovery.h"
#include "production_logger.h"

// Critical files that must be protected
const char* CRITICAL_FILES[] = {
  "/device_config.json",
  "/security_config.json", 
  "/wifi_credentials.json",
  "/emergency.log",
  "/logs/critical.log",
  "/recovery_state.json"
};
const int CRITICAL_FILES_COUNT = 6;

// Static member initialization
SPIFFSHealth SPIFFSRecovery::health = {};
Preferences SPIFFSRecovery::recoveryPrefs;
bool SPIFFSRecovery::emergencyMode = false;
String SPIFFSRecovery::backupPath = "/backup";
unsigned long SPIFFSRecovery::lastHealthCheck = 0;
const unsigned long SPIFFSRecovery::HEALTH_CHECK_INTERVAL = 60000; // 1 minute

bool SPIFFSRecovery::init() {
  LOG_INFO(LOG_SYSTEM, "Initializing SPIFFS recovery system");
  
  // Initialize preferences for recovery tracking
  recoveryPrefs.begin("spiffs_recovery", false);
  
  // Check if we're recovering from a power failure
  bool powerFailureRecovery = recoveryPrefs.getBool("power_failure", false);
  if (powerFailureRecovery) {
    LOG_CRITICAL(LOG_SYSTEM, "Recovering from power failure");
    if (!recoverFromPowerFailure()) {
      LOG_CRITICAL(LOG_SYSTEM, "Power failure recovery failed");
    }
    recoveryPrefs.putBool("power_failure", false);
  }
  
  // Try to mount SPIFFS
  if (!SPIFFS.begin(true)) {
    LOG_CRITICAL(LOG_HARDWARE, "SPIFFS mount failed, attempting recovery");
    
    // Try recovery procedures
    RecoveryAction action = diagnoseAndRecover();
    if (!performRecovery(action)) {
      LOG_EMERGENCY("SPIFFS recovery failed - entering emergency mode");
      enableEmergencyMode();
      return false;
    }
  }
  
  // Validate filesystem integrity
  if (!validateFileSystem()) {
    LOG_ERROR(LOG_HARDWARE, "SPIFFS validation failed");
    enableEmergencyMode();
    return false;
  }
  
  // Create backup directory
  SPIFFS.mkdir(backupPath);
  
  // Backup critical files on startup
  backupCriticalFiles();
  
  // Initial health check
  health = checkHealth();
  
  LOG_INFO(LOG_SYSTEM, "SPIFFS recovery system initialized", 
           "status=" + String(health.status) + ", space=" + String(health.freeBytes));
  
  return true;
}

SPIFFSHealth SPIFFSRecovery::checkHealth() {
  SPIFFSHealth currentHealth = {};
  currentHealth.lastCheck = millis();
  
  if (emergencyMode) {
    currentHealth.status = SPIFFS_CRITICAL_ERROR;
    return currentHealth;
  }
  
  // Basic filesystem stats
  currentHealth.totalBytes = SPIFFS.totalBytes();
  currentHealth.usedBytes = SPIFFS.usedBytes();
  currentHealth.freeBytes = currentHealth.totalBytes - currentHealth.usedBytes;
  
  // Count files
  File root = SPIFFS.open("/");
  currentHealth.fileCount = 0;
  if (root && root.isDirectory()) {
    File file = root.openNextFile();
    while (file) {
      currentHealth.fileCount++;
      file = root.openNextFile();
    }
    root.close();
  }
  
  // Test write capability
  String testFile = "/test_write.tmp";
  File test = SPIFFS.open(testFile, FILE_WRITE);
  if (test) {
    test.println("test");
    test.close();
    currentHealth.canWrite = true;
    SPIFFS.remove(testFile);
  } else {
    currentHealth.canWrite = false;
  }
  
  // Test read capability  
  currentHealth.canRead = SPIFFS.exists("/");
  
  // Determine overall status
  if (!currentHealth.canRead || !currentHealth.canWrite) {
    currentHealth.status = SPIFFS_CORRUPTED;
  } else if (currentHealth.freeBytes < 1024) { // Less than 1KB free
    currentHealth.status = SPIFFS_FULL;
  } else {
    currentHealth.status = SPIFFS_OK;
  }
  
  // Track error history
  if (currentHealth.status != SPIFFS_OK) {
    currentHealth.errorCount = recoveryPrefs.getInt("error_count", 0) + 1;
    recoveryPrefs.putInt("error_count", currentHealth.errorCount);
  }
  
  currentHealth.recoveryCount = recoveryPrefs.getInt("recovery_count", 0);
  
  return currentHealth;
}

bool SPIFFSRecovery::isHealthy() {
  if (millis() - lastHealthCheck > HEALTH_CHECK_INTERVAL) {
    health = checkHealth();
    lastHealthCheck = millis();
  }
  
  return health.status == SPIFFS_OK && !emergencyMode;
}

void SPIFFSRecovery::periodicHealthCheck() {
  if (millis() - lastHealthCheck < HEALTH_CHECK_INTERVAL) {
    return;
  }
  
  SPIFFSHealth newHealth = checkHealth();
  
  // Compare with previous health state
  if (newHealth.status != health.status) {
    LOG_WARNING(LOG_HARDWARE, "SPIFFS health changed", 
                "old=" + String(health.status) + ", new=" + String(newHealth.status));
    
    if (newHealth.status != SPIFFS_OK) {
      // Attempt immediate recovery
      RecoveryAction action = diagnoseAndRecover();
      performRecovery(action);
    }
  }
  
  // Check for critically low space
  if (newHealth.freeBytes < 2048 && health.freeBytes >= 2048) {
    LOG_WARNING(LOG_HARDWARE, "SPIFFS space critically low", "free=" + String(newHealth.freeBytes));
    // Try to clean up old logs
    cleanupOldFiles();
  }
  
  health = newHealth;
}

File SPIFFSRecovery::safeOpen(const String& path, const char* mode) {
  if (emergencyMode) {
    LOG_ERROR(LOG_HARDWARE, "Cannot open file in emergency mode", "path=" + path);
    return File();
  }
  
  // Check health before attempting operation
  if (!isHealthy()) {
    LOG_WARNING(LOG_HARDWARE, "SPIFFS unhealthy, attempting recovery before file operation");
    RecoveryAction action = diagnoseAndRecover();
    if (!performRecovery(action)) {
      return File();
    }
  }
  
  // Mark operation start (for power failure recovery)
  markOperationStart("open:" + path);
  
  File file = SPIFFS.open(path, mode);
  
  // Mark operation complete
  markOperationComplete("open:" + path);
  
  if (!file) {
    LOG_ERROR(LOG_HARDWARE, "Failed to open file", "path=" + path + ", mode=" + String(mode));
  }
  
  return file;
}

bool SPIFFSRecovery::safeWrite(const String& path, const String& data) {
  if (emergencyMode) {
    LOG_ERROR(LOG_HARDWARE, "Cannot write in emergency mode", "path=" + path);
    handleEmergencyStorage(); // Store in preferences instead
    return false;
  }
  
  markOperationStart("write:" + path);
  
  File file = safeOpen(path, FILE_WRITE);
  if (!file) {
    markOperationComplete("write:" + path);
    return false;
  }
  
  size_t written = file.print(data);
  file.close();
  
  markOperationComplete("write:" + path);
  
  bool success = (written == data.length());
  if (!success) {
    LOG_ERROR(LOG_HARDWARE, "Incomplete write operation", 
              "path=" + path + ", expected=" + String(data.length()) + ", written=" + String(written));
  }
  
  return success;
}

String SPIFFSRecovery::safeRead(const String& path) {
  if (emergencyMode) {
    LOG_ERROR(LOG_HARDWARE, "Cannot read in emergency mode", "path=" + path);
    return "";
  }
  
  File file = safeOpen(path, FILE_READ);
  if (!file) {
    return "";
  }
  
  String content = file.readString();
  file.close();
  
  return content;
}

bool SPIFFSRecovery::atomicWrite(const String& path, const String& data) {
  // Atomic write: write to temporary file first, then rename
  String tempPath = path + ".tmp";
  
  markOperationStart("atomic_write:" + path);
  
  // Write to temporary file
  if (!safeWrite(tempPath, data)) {
    markOperationComplete("atomic_write:" + path);
    return false;
  }
  
  // Verify temporary file
  String verification = safeRead(tempPath);
  if (verification != data) {
    LOG_ERROR(LOG_HARDWARE, "Atomic write verification failed", "path=" + path);
    SPIFFS.remove(tempPath);
    markOperationComplete("atomic_write:" + path);
    return false;
  }
  
  // Remove old file and rename temp file
  if (SPIFFS.exists(path)) {
    SPIFFS.remove(path);
  }
  
  bool success = SPIFFS.rename(tempPath, path);
  markOperationComplete("atomic_write:" + path);
  
  if (!success) {
    LOG_ERROR(LOG_HARDWARE, "Atomic write rename failed", "path=" + path);
    SPIFFS.remove(tempPath);
  }
  
  return success;
}

RecoveryAction SPIFFSRecovery::diagnoseAndRecover() {
  LOG_INFO(LOG_HARDWARE, "Diagnosing SPIFFS problems");
  
  // Check if SPIFFS is mounted
  if (!SPIFFS.begin(false)) {
    LOG_ERROR(LOG_HARDWARE, "SPIFFS not mounted, attempting remount");
    return RECOVERY_REMOUNT;
  }
  
  SPIFFSHealth currentHealth = checkHealth();
  
  switch (currentHealth.status) {
    case SPIFFS_OK:
      return RECOVERY_NONE;
      
    case SPIFFS_CORRUPTED:
      LOG_ERROR(LOG_HARDWARE, "SPIFFS corrupted, attempting format");
      return RECOVERY_FORMAT;
      
    case SPIFFS_FULL:
      LOG_WARNING(LOG_HARDWARE, "SPIFFS full, cleaning up");
      cleanupOldFiles();
      return RECOVERY_NONE;
      
    case SPIFFS_MOUNT_FAILED:
      return RECOVERY_REMOUNT;
      
    default:
      LOG_CRITICAL(LOG_HARDWARE, "SPIFFS critical error, attempting factory reset");
      return RECOVERY_FACTORY_RESET;
  }
}

bool SPIFFSRecovery::performRecovery(RecoveryAction action) {
  LOG_INFO(LOG_HARDWARE, "Performing recovery", "action=" + String(action));
  
  bool success = false;
  
  switch (action) {
    case RECOVERY_NONE:
      success = true;
      break;
      
    case RECOVERY_REMOUNT:
      success = attemptRemount();
      break;
      
    case RECOVERY_FORMAT:
      // Backup critical files first
      backupCriticalFiles();
      success = attemptFormat();
      if (success) {
        restoreCriticalFiles();
      }
      break;
      
    case RECOVERY_BACKUP_RESTORE:
      success = restoreFromBackup();
      break;
      
    case RECOVERY_FACTORY_RESET:
      LOG_CRITICAL(LOG_HARDWARE, "Performing factory reset recovery");
      success = attemptFormat();
      // Don't restore files in factory reset
      break;
  }
  
  if (success) {
    int recoveryCount = recoveryPrefs.getInt("recovery_count", 0) + 1;
    recoveryPrefs.putInt("recovery_count", recoveryCount);
    disableEmergencyMode();
  } else {
    enableEmergencyMode();
  }
  
  logRecoveryAction(action, success);
  return success;
}

bool SPIFFSRecovery::attemptRemount() {
  SPIFFS.end();
  delay(100);
  
  bool success = SPIFFS.begin(true);
  if (success) {
    LOG_INFO(LOG_HARDWARE, "SPIFFS remount successful");
  } else {
    LOG_ERROR(LOG_HARDWARE, "SPIFFS remount failed");
  }
  
  return success;
}

bool SPIFFSRecovery::attemptFormat() {
  LOG_WARNING(LOG_HARDWARE, "Formatting SPIFFS - all data will be lost");
  
  SPIFFS.end();
  delay(100);
  
  bool success = SPIFFS.format();
  if (success) {
    success = SPIFFS.begin(true);
    if (success) {
      // Create essential directories
      SPIFFS.mkdir("/logs");
      SPIFFS.mkdir("/backup");
      SPIFFS.mkdir("/config");
    }
  }
  
  if (success) {
    LOG_INFO(LOG_HARDWARE, "SPIFFS format and remount successful");
  } else {
    LOG_CRITICAL(LOG_HARDWARE, "SPIFFS format failed");
  }
  
  return success;
}

bool SPIFFSRecovery::backupCriticalFiles() {
  LOG_INFO(LOG_SYSTEM, "Backing up critical files");
  
  bool allSuccess = true;
  
  for (int i = 0; i < CRITICAL_FILES_COUNT; i++) {
    String filePath = CRITICAL_FILES[i];
    
    if (!SPIFFS.exists(filePath)) {
      continue; // Skip files that don't exist
    }
    
    String backupFilePath = backupPath + filePath + ".bak";
    
    // Create backup directory structure
    int lastSlash = backupFilePath.lastIndexOf('/');
    if (lastSlash > 0) {
      String backupDir = backupFilePath.substring(0, lastSlash);
      SPIFFS.mkdir(backupDir);
    }
    
    // Copy file
    File source = SPIFFS.open(filePath, FILE_READ);
    File backup = SPIFFS.open(backupFilePath, FILE_WRITE);
    
    if (source && backup) {
      while (source.available()) {
        backup.write(source.read());
      }
      source.close();
      backup.close();
      LOG_DEBUG(LOG_SYSTEM, "Backed up file", "path=" + filePath);
    } else {
      LOG_ERROR(LOG_SYSTEM, "Failed to backup file", "path=" + filePath);
      allSuccess = false;
    }
    
    if (source) source.close();
    if (backup) backup.close();
  }
  
  return allSuccess;
}

bool SPIFFSRecovery::restoreCriticalFiles() {
  LOG_INFO(LOG_SYSTEM, "Restoring critical files from backup");
  
  bool allSuccess = true;
  
  for (int i = 0; i < CRITICAL_FILES_COUNT; i++) {
    String filePath = CRITICAL_FILES[i];
    String backupFilePath = backupPath + filePath + ".bak";
    
    if (!SPIFFS.exists(backupFilePath)) {
      continue; // Skip if no backup exists
    }
    
    // Create target directory structure
    int lastSlash = filePath.lastIndexOf('/');
    if (lastSlash > 0) {
      String targetDir = filePath.substring(0, lastSlash);
      SPIFFS.mkdir(targetDir);
    }
    
    // Copy backup to original location
    File backup = SPIFFS.open(backupFilePath, FILE_READ);
    File target = SPIFFS.open(filePath, FILE_WRITE);
    
    if (backup && target) {
      while (backup.available()) {
        target.write(backup.read());
      }
      backup.close();
      target.close();
      LOG_DEBUG(LOG_SYSTEM, "Restored file", "path=" + filePath);
    } else {
      LOG_ERROR(LOG_SYSTEM, "Failed to restore file", "path=" + filePath);
      allSuccess = false;
    }
    
    if (backup) backup.close();
    if (target) target.close();
  }
  
  return allSuccess;
}

bool SPIFFSRecovery::validateFileSystem() {
  // Basic validation tests
  
  // Test directory listing
  File root = SPIFFS.open("/");
  if (!root || !root.isDirectory()) {
    LOG_ERROR(LOG_HARDWARE, "Cannot open root directory");
    return false;
  }
  root.close();
  
  // Test write/read cycle
  String testPath = "/validation_test.tmp";
  String testData = "filesystem_validation_" + String(millis());
  
  if (!safeWrite(testPath, testData)) {
    LOG_ERROR(LOG_HARDWARE, "Validation write test failed");
    return false;
  }
  
  String readData = safeRead(testPath);
  SPIFFS.remove(testPath);
  
  if (readData != testData) {
    LOG_ERROR(LOG_HARDWARE, "Validation read test failed");
    return false;
  }
  
  LOG_DEBUG(LOG_HARDWARE, "SPIFFS validation passed");
  return true;
}

void SPIFFSRecovery::enableEmergencyMode() {
  emergencyMode = true;
  recoveryPrefs.putBool("emergency_mode", true);
  LOG_EMERGENCY("Emergency mode activated - SPIFFS operations disabled");
}

void SPIFFSRecovery::disableEmergencyMode() {
  if (emergencyMode) {
    emergencyMode = false;
    recoveryPrefs.putBool("emergency_mode", false);
    LOG_INFO(LOG_SYSTEM, "Emergency mode deactivated");
  }
}

void SPIFFSRecovery::handleEmergencyStorage() {
  // In emergency mode, critical data is stored in Preferences (NVS)
  // This is limited but more reliable than corrupted SPIFFS
  
  LOG_WARNING(LOG_HARDWARE, "Using emergency storage (Preferences)");
  
  // Store minimal critical state in NVS
  Preferences emergency;
  emergency.begin("emergency", false);
  emergency.putULong("emergency_time", millis());
  emergency.putString("emergency_reason", "spiffs_failure");
  emergency.end();
}

bool SPIFFSRecovery::recoverFromPowerFailure() {
  LOG_INFO(LOG_SYSTEM, "Recovering from power failure");
  
  // Check for incomplete operations
  return checkForIncompleteOperations();
}

bool SPIFFSRecovery::checkForIncompleteOperations() {
  Preferences opPrefs;
  opPrefs.begin("operations", false);
  
  String activeOp = opPrefs.getString("active_operation", "");
  if (activeOp.isEmpty()) {
    opPrefs.end();
    return true; // No incomplete operations
  }
  
  LOG_WARNING(LOG_SYSTEM, "Found incomplete operation", "operation=" + activeOp);
  
  // Try to clean up incomplete operation
  if (activeOp.startsWith("write:") || activeOp.startsWith("atomic_write:")) {
    String path = activeOp.substring(activeOp.indexOf(':') + 1);
    String tempPath = path + ".tmp";
    
    if (SPIFFS.exists(tempPath)) {
      SPIFFS.remove(tempPath);
      LOG_INFO(LOG_SYSTEM, "Cleaned up temporary file", "path=" + tempPath);
    }
  }
  
  // Clear the active operation
  opPrefs.remove("active_operation");
  opPrefs.end();
  
  return true;
}

void SPIFFSRecovery::markOperationStart(const String& operation) {
  // Mark power failure detection
  recoveryPrefs.putBool("power_failure", true);
  
  Preferences opPrefs;
  opPrefs.begin("operations", false);
  opPrefs.putString("active_operation", operation);
  opPrefs.putULong("operation_start", millis());
  opPrefs.end();
}

void SPIFFSRecovery::markOperationComplete(const String& operation) {
  Preferences opPrefs;
  opPrefs.begin("operations", false);
  opPrefs.remove("active_operation");
  opPrefs.end();
  
  // Clear power failure flag
  recoveryPrefs.putBool("power_failure", false);
}

void SPIFFSRecovery::logRecoveryAction(RecoveryAction action, bool success) {
  String actionName;
  switch (action) {
    case RECOVERY_NONE: actionName = "none"; break;
    case RECOVERY_REMOUNT: actionName = "remount"; break;
    case RECOVERY_FORMAT: actionName = "format"; break;
    case RECOVERY_BACKUP_RESTORE: actionName = "backup_restore"; break;
    case RECOVERY_FACTORY_RESET: actionName = "factory_reset"; break;
    default: actionName = "unknown"; break;
  }
  
  if (success) {
    LOG_INFO(LOG_HARDWARE, "Recovery action successful", "action=" + actionName);
  } else {
    LOG_ERROR(LOG_HARDWARE, "Recovery action failed", "action=" + actionName);
  }
}

void SPIFFSRecovery::cleanupOldFiles() {
  LOG_INFO(LOG_SYSTEM, "Cleaning up old files to free space");
  
  // Remove old backup files
  File backupDir = SPIFFS.open(backupPath);
  if (backupDir && backupDir.isDirectory()) {
    File file = backupDir.openNextFile();
    while (file) {
      if (!file.isDirectory()) {
        SPIFFS.remove(backupPath + "/" + file.name());
        LOG_DEBUG(LOG_SYSTEM, "Removed old backup", "file=" + String(file.name()));
      }
      file = backupDir.openNextFile();
    }
    backupDir.close();
  }
  
  // Remove temporary files
  File root = SPIFFS.open("/");
  if (root && root.isDirectory()) {
    File file = root.openNextFile();
    while (file) {
      String fileName = file.name();
      if (fileName.endsWith(".tmp") || fileName.endsWith(".bak")) {
        SPIFFS.remove("/" + fileName);
        LOG_DEBUG(LOG_SYSTEM, "Removed temporary file", "file=" + fileName);
      }
      file = root.openNextFile();
    }
    root.close();
  }
}

SPIFFSHealth SPIFFSRecovery::getHealthStatus() {
  return health;
}

void SPIFFSRecovery::printHealthReport() {
  // Only print in development mode
  #if !PRODUCTION_MODE
  Serial.println("=== SPIFFS Health Report ===");
  Serial.printf("Status: %d\n", health.status);
  Serial.printf("Total: %zu bytes\n", health.totalBytes);
  Serial.printf("Used: %zu bytes\n", health.usedBytes);
  Serial.printf("Free: %zu bytes\n", health.freeBytes);
  Serial.printf("Files: %d\n", health.fileCount);
  Serial.printf("Can Write: %s\n", health.canWrite ? "Yes" : "No");
  Serial.printf("Can Read: %s\n", health.canRead ? "Yes" : "No");
  Serial.printf("Errors: %d\n", health.errorCount);
  Serial.printf("Recoveries: %d\n", health.recoveryCount);
  Serial.printf("Emergency Mode: %s\n", emergencyMode ? "Yes" : "No");
  Serial.println("============================");
  #endif
}