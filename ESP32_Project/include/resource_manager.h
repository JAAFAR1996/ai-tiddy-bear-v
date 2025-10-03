#ifndef RESOURCE_MANAGER_H
#define RESOURCE_MANAGER_H

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

// Resource tracking configuration
#define MAX_TRACKED_RESOURCES 100
#define POOL_ALLOCATION_THRESHOLD 512  // Use pool for allocations <= 512 bytes
#define LOW_MEMORY_THRESHOLD 10000     // Consider memory low below 10KB
#define MEMORY_LEAK_THRESHOLD 300000   // 5 minutes in milliseconds

// Resource tracking structure
struct ResourceTracker {
  void* ptr;
  size_t size;
  unsigned long timestamp;
  char name[32];
};

// Resource statistics structure
struct ResourceStats {
    uint32_t heapFragmentation;
    uint32_t gcRunCount;
    uint32_t allocCount;
    uint32_t totalHeap;
    uint32_t minFreeHeap;
    size_t trackedAllocations;
    size_t trackedMemory;
    unsigned long lastGC;
};

// Resource Manager API
bool initResourceManager();
void cleanupResourceManager();

// Enhanced memory allocation with tracking
void* trackMalloc(size_t size, const char* name);
void trackFree(void* ptr, const char* name = nullptr);

// Convenience macros for tracked allocation
#define TRACK_MALLOC(size, name) trackMalloc(size, name)
#define TRACK_FREE(ptr, name) trackFree(ptr, name)
#define TRACK_NEW(type, name) (type*)trackMalloc(sizeof(type), name)
#define TRACK_DELETE(ptr, name) trackFree(ptr, name)

// Resource tracking functions
bool addResourceTracker(void* ptr, size_t size, const char* name);
bool removeResourceTracker(void* ptr);

// Memory management functions
void printResourceStatus();
void detectMemoryLeaks();
void forceGarbageCollection();
size_t getAvailableMemory();
size_t getTotalAllocatedMemory();
bool isMemoryLow();
void emergencyCleanup();

// RAII helper class for automatic resource management
class ScopedResource {
private:
  void* ptr;
  const char* name;
  
public:
  ScopedResource(size_t size, const char* resourceName) 
    : name(resourceName) {
    ptr = trackMalloc(size, name);
  }
  
  ~ScopedResource() {
    if (ptr) {
      trackFree(ptr, name);
    }
  }
  
  void* get() { return ptr; }
  bool isValid() { return ptr != nullptr; }
  
  // Prevent copying
  ScopedResource(const ScopedResource&) = delete;
  ScopedResource& operator=(const ScopedResource&) = delete;
};

// Smart pointer-like class for managed memory
template<typename T>
class ManagedPtr {
private:
  T* ptr;
  const char* name;
  
public:
  ManagedPtr(const char* resourceName) : name(resourceName) {
    ptr = (T*)trackMalloc(sizeof(T), name);
  }
  
  ~ManagedPtr() {
    if (ptr) {
      trackFree(ptr, name);
    }
  }
  
  T* get() { return ptr; }
  T& operator*() { return *ptr; }
  T* operator->() { return ptr; }
  bool isValid() { return ptr != nullptr; }
  
  // Prevent copying
  ManagedPtr(const ManagedPtr&) = delete;
  ManagedPtr& operator=(const ManagedPtr&) = delete;
};

// Memory pool management
class MemoryPool {
private:
  uint8_t* pool;
  size_t size;
  size_t used;
  bool* allocation_map;
  size_t block_size;
  size_t num_blocks;
  
public:
  MemoryPool(size_t poolSize, size_t blockSize);
  ~MemoryPool();
  
  void* allocate();
  void deallocate(void* ptr);
  size_t getFreeBlocks();
  size_t getUsedBlocks();
  void printStatus();
};

// Helper functions for memory monitoring
void setupMemoryMonitoring();
void handleMemoryWarning();
void handleMemoryCritical();

// Memory health check
struct MemoryHealthInfo {
  size_t free_heap;
  size_t min_free_heap;
  size_t total_heap;
  size_t tracked_allocations;
  size_t tracked_memory;
  int potential_leaks;
  bool memory_low;
  bool memory_critical;
};

MemoryHealthInfo getMemoryHealth();
void printMemoryHealth();

// ResourceManager class
class ResourceManager {
public:
    bool init();
    void cleanup();
    ResourceStats getResourceStats();
    size_t getTrackedAllocations();
    void performMaintenance();
    void printStatus();
    
private:
    ResourceStats stats;
    void updateStats();
};

// Global instance
extern ResourceManager resourceManager;

#endif