#ifndef REALTIME_AUDIO_STREAMER_H
#define REALTIME_AUDIO_STREAMER_H

#include "config.h"
#include "audio_handler.h"
#include "websocket_handler.h"
#include <driver/i2s.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <freertos/ringbuf.h>

// Real-time Audio Streaming Configuration
#define RTS_SAMPLE_RATE         16000     // Hz - Sample rate
#define RTS_CHUNK_SIZE          4096      // bytes - 4096-byte chunks as specified
#define RTS_RING_BUFFER_SIZE    (16384)   // 16KB ring buffer (reduced from 32KB for memory optimization)
#define RTS_MIN_CHUNK_SIZE      512       // Minimum chunk size for poor network
#define RTS_MAX_CHUNK_SIZE      8192      // Maximum chunk size for excellent network
#define RTS_LATENCY_TARGET      100       // Target latency in milliseconds
#define RTS_VAD_FRAME_SIZE      320       // VAD analysis frame size (20ms at 16kHz)
#define RTS_SILENCE_THRESHOLD   800       // Silence detection threshold
#define RTS_CONTINUOUS_SILENCE_LIMIT 5000 // Max continuous silence in ms before pausing

// Network adaptive parameters
#define RTS_NETWORK_CHECK_INTERVAL 5000   // Network condition check interval (ms)
#define RTS_CHUNK_ADJUSTMENT_THRESHOLD 3  // Failures before chunk size adjustment
#define RTS_GOOD_NETWORK_RSSI    -50      // dBm - Excellent signal threshold
#define RTS_FAIR_NETWORK_RSSI    -70      // dBm - Fair signal threshold

// Audio processing states
enum RTSState {
    RTS_IDLE,
    RTS_INITIALIZING,
    RTS_STREAMING,
    RTS_PAUSED_SILENCE,
    RTS_ERROR,
    RTS_STOPPING
};

// Network condition levels
enum NetworkCondition {
    NETWORK_EXCELLENT,
    NETWORK_GOOD,
    NETWORK_FAIR,
    NETWORK_POOR
};

// Audio chunk metadata
struct AudioChunk {
    uint8_t* data;
    size_t size;
    uint32_t timestamp;
    uint16_t sequence;
    bool hasVoice;
};

// Real-time performance metrics
struct RTSMetrics {
    uint32_t chunksProcessed;
    uint32_t chunksSent;
    uint32_t chunksDropped;
    uint32_t totalLatency;
    uint32_t averageLatency;
    uint32_t networkRetries;
    float averageChunkSize;
    uint32_t voiceChunks;
    uint32_t silenceChunks;
    uint32_t lastMetricsReset;
};

// Network adaptation state
struct NetworkState {
    NetworkCondition condition;
    size_t currentChunkSize;
    uint32_t consecutiveFailures;
    uint32_t lastNetworkCheck;
    int32_t currentRSSI;
    uint32_t adaptiveDelay;
    bool canIncreaseChunkSize;
};

class RealtimeAudioStreamer {
public:
    // Constructor and destructor
    RealtimeAudioStreamer();
    ~RealtimeAudioStreamer();
    
    // Core streaming functions
    bool init();
    bool startStreaming();
    void stopStreaming();
    bool isStreaming();
    void processIncomingAudio(uint8_t* audioData, size_t length);
    
    // State management
    RTSState getState() const { return currentState; }
    void setState(RTSState newState);
    
    // Network adaptation
    void updateNetworkConditions();
    size_t getOptimalChunkSize();
    void adjustChunkSize(bool increase);
    
    // Performance metrics
    const RTSMetrics& getMetrics() const { return metrics; }
    void resetMetrics();
    void printMetrics();
    
    // Configuration
    void setLatencyTarget(uint32_t targetMs) { latencyTarget = targetMs; }
    void setSilenceThreshold(uint16_t threshold) { silenceThreshold = threshold; }
    void setChunkSize(size_t size);
    
    // Cleanup
    void cleanup();

private:
    // Core streaming implementation
    void audioStreamingTask();
    static void audioStreamingTaskWrapper(void* parameter);
    
    // Audio processing
    bool detectVoiceActivity(int16_t* samples, size_t count);
    void processAudioChunk(uint8_t* chunk, size_t size);
    bool applyRealTimeEnhancements(int16_t* samples, size_t count);
    
    // Network transmission
    void sendAudioChunk(uint8_t* chunk, size_t size);
    void handleServerAudioResponse(uint8_t* audioData, size_t length);
    bool sendChunkWithRetry(const AudioChunk& chunk, uint8_t maxRetries = 3);
    
    // Ring buffer operations
    bool initRingBuffers();
    void cleanupRingBuffers();
    bool writeToInputBuffer(const uint8_t* data, size_t size);
    size_t readFromInputBuffer(uint8_t* data, size_t maxSize);
    bool isInputBufferEmpty();
    size_t getInputBufferFreeSpace();
    
    // Dynamic silence detection
    void updateSilenceDetection();
    bool isCurrentlySilent();
    void handleSilencePeriod();
    void handleVoicePeriod();
    
    // Performance optimization
    void optimizeForLatency();
    void adjustForNetworkConditions();
    uint32_t calculateCurrentLatency();
    void updatePerformanceMetrics();
    
    // Error handling and recovery
    void handleTransmissionError();
    void attemptRecovery();
    bool validateAudioData(const uint8_t* data, size_t size);

private:
    // State variables
    RTSState currentState;
    bool initialized;
    bool streaming;
    
    // FreeRTOS resources
    TaskHandle_t streamingTaskHandle;
    SemaphoreHandle_t stateMutex;
    QueueHandle_t audioQueue;
    RingbufHandle_t inputRingBuffer;
    RingbufHandle_t outputRingBuffer;
    
    // Audio configuration
    uint32_t sampleRate;
    size_t baseChunkSize;
    uint32_t latencyTarget;
    uint16_t silenceThreshold;
    
    // Ring buffer configuration
    uint8_t* inputBuffer;
    uint8_t* outputBuffer;
    size_t ringBufferSize;
    
    // Voice Activity Detection
    VADMetrics realTimeVAD;
    uint32_t continuousSilenceTime;
    uint32_t lastVoiceActivity;
    bool silenceDetectionEnabled;
    
    // Network adaptation
    NetworkState networkState;
    uint32_t networkCheckInterval;
    
    // Performance tracking
    RTSMetrics metrics;
    uint32_t lastChunkTime;
    uint16_t sequenceNumber;
    
    // Audio processing
    int16_t* processingBuffer;
    size_t processingBufferSize;
    NoiseProfile realtimeNoiseProfile;
    AGCState realtimeAGC;
    
    // Timing and synchronization
    uint32_t streamingStartTime;
    uint32_t lastNetworkUpdate;
    uint32_t lastPerformanceUpdate;
    
    // Error handling
    uint8_t consecutiveErrors;
    uint32_t lastErrorTime;
    uint8_t maxConsecutiveErrors;
};

// Global instance declaration
extern RealtimeAudioStreamer realtimeStreamer;

// C-style wrapper functions for integration
extern "C" {
    bool initRealtimeStreaming();
    bool startRealtimeStreaming();
    void stopRealtimeStreaming();
    bool isRealtimeStreaming();
    void processIncomingRealtimeAudio(uint8_t* audioData, size_t length);
    void printRealtimeStreamingMetrics();
    void cleanupRealtimeStreaming();
}

// Performance monitoring integration
void recordAudioLatency(uint32_t latencyMs);
void updateStreamingQualityScore(float score);

// Network callback for adaptive streaming
void onNetworkConditionChanged(NetworkCondition newCondition);

#endif // REALTIME_AUDIO_STREAMER_H