#include "realtime_audio_streamer.h"
#include "websocket_handler.h"
#include "hardware.h"
#include "monitoring.h"
#include "encoding_service.h"
#include "device_id_manager.h"  // Dynamic device ID
#include <WiFi.h>
#include <ArduinoJson.h>
#include <math.h>

// Global instance
RealtimeAudioStreamer realtimeStreamer;

// Static task configuration
static const uint32_t STREAMING_TASK_STACK_SIZE = 8192;
static const UBaseType_t STREAMING_TASK_PRIORITY = 5;  // High priority for real-time processing
static const uint32_t AUDIO_QUEUE_LENGTH = 10;
static const uint32_t AUDIO_QUEUE_ITEM_SIZE = sizeof(AudioChunk);

// Performance monitoring variables

// =============================================================================
// CONSTRUCTOR AND INITIALIZATION
// =============================================================================

RealtimeAudioStreamer::RealtimeAudioStreamer() {
    currentState = RTS_IDLE;
    initialized = false;
    streaming = false;
    
    // Initialize handles to NULL
    streamingTaskHandle = NULL;
    stateMutex = NULL;
    audioQueue = NULL;
    inputRingBuffer = NULL;
    outputRingBuffer = NULL;
    
    // Initialize configuration
    sampleRate = RTS_SAMPLE_RATE;
    baseChunkSize = RTS_CHUNK_SIZE;
    latencyTarget = RTS_LATENCY_TARGET;
    silenceThreshold = RTS_SILENCE_THRESHOLD;
    ringBufferSize = RTS_RING_BUFFER_SIZE;
    
    // Initialize buffers
    inputBuffer = nullptr;
    outputBuffer = nullptr;
    processingBuffer = nullptr;
    processingBufferSize = 0;
    
    // Initialize metrics
    memset(&metrics, 0, sizeof(RTSMetrics));
    metrics.lastMetricsReset = millis();
    
    // Initialize network state
    networkState.condition = NETWORK_GOOD;
    networkState.currentChunkSize = baseChunkSize;
    networkState.consecutiveFailures = 0;
    networkState.lastNetworkCheck = 0;
    networkState.adaptiveDelay = 10; // 10ms default
    networkState.canIncreaseChunkSize = true;
    
    // Initialize VAD
    memset(&realTimeVAD, 0, sizeof(VADMetrics));
    realTimeVAD.state = VAD_UNKNOWN;
    continuousSilenceTime = 0;
    lastVoiceActivity = 0;
    silenceDetectionEnabled = true;
    
    // Initialize timing
    sequenceNumber = 0;
    lastChunkTime = 0;
    streamingStartTime = 0;
    lastNetworkUpdate = 0;
    lastPerformanceUpdate = 0;
    
    // Initialize error handling
    consecutiveErrors = 0;
    lastErrorTime = 0;
    maxConsecutiveErrors = 5;
    
    networkCheckInterval = RTS_NETWORK_CHECK_INTERVAL;
}

RealtimeAudioStreamer::~RealtimeAudioStreamer() {
    // Ensure streaming is stopped
    stopStreaming();
    
    // Clean up resources
    cleanup();
    
    // Clean up mutex
    if (stateMutex != NULL) {
        vSemaphoreDelete(stateMutex);
        stateMutex = NULL;
    }
}

bool RealtimeAudioStreamer::init() {
    Serial.println("🎤 Initializing Real-time Audio Streamer...");
    
    if (initialized) {
        Serial.println("⚠️ Already initialized");
        return true;
    }
    
    setState(RTS_INITIALIZING);
    
    // Create mutex for thread safety
    stateMutex = xSemaphoreCreateMutex();
    if (stateMutex == NULL) {
        Serial.println("❌ Failed to create state mutex");
        setState(RTS_ERROR);
        return false;
    }
    
    // Initialize ring buffers
    if (!initRingBuffers()) {
        Serial.println("❌ Failed to initialize ring buffers");
        setState(RTS_ERROR);
        return false;
    }
    
    // Create audio processing queue
    audioQueue = xQueueCreate(AUDIO_QUEUE_LENGTH, AUDIO_QUEUE_ITEM_SIZE);
    if (audioQueue == NULL) {
        Serial.println("❌ Failed to create audio queue");
        cleanup();
        setState(RTS_ERROR);
        return false;
    }
    
    // Allocate processing buffer
    processingBufferSize = RTS_CHUNK_SIZE / 2; // 16-bit samples
    processingBuffer = (int16_t*)malloc(processingBufferSize * sizeof(int16_t));
    if (processingBuffer == nullptr) {
        Serial.println("❌ Failed to allocate processing buffer");
        cleanup();
        setState(RTS_ERROR);
        return false;
    }
    
    // Initialize real-time audio enhancements
    realtimeNoiseProfile = {};
    realtimeAGC = {};
    
    // Initialize AGC for real-time use
    realtimeAGC.current_gain = 1.0f;
    realtimeAGC.peak_level = 0.0f;
    realtimeAGC.rms_level = 0.0f;
    realtimeAGC.attack_time = 0.05f;   // Fast attack for real-time
    realtimeAGC.release_time = 0.95f;  // Slow release
    
    initialized = true;
    setState(RTS_IDLE);
    
    Serial.println("✅ Real-time Audio Streamer initialized successfully");
    Serial.printf("📊 Configuration: Sample Rate=%dHz, Chunk Size=%d bytes, Target Latency=%dms\n", 
                  sampleRate, baseChunkSize, latencyTarget);
    
    return true;
}

// =============================================================================
// RING BUFFER MANAGEMENT
// =============================================================================

bool RealtimeAudioStreamer::initRingBuffers() {
    Serial.println("🔄 Initializing ring buffers...");
    
    // Create input ring buffer
    inputRingBuffer = xRingbufferCreate(ringBufferSize, RINGBUF_TYPE_BYTEBUF);
    if (inputRingBuffer == NULL) {
        Serial.println("❌ Failed to create input ring buffer");
        return false;
    }
    
    // Create output ring buffer (for server audio responses)
    outputRingBuffer = xRingbufferCreate(ringBufferSize / 2, RINGBUF_TYPE_BYTEBUF);
    if (outputRingBuffer == NULL) {
        Serial.println("❌ Failed to create output ring buffer");
        vRingbufferDelete(inputRingBuffer);
        inputRingBuffer = NULL;
        return false;
    }
    
    Serial.printf("✅ Ring buffers created: Input=%d bytes, Output=%d bytes\n", 
                  ringBufferSize, ringBufferSize / 2);
    return true;
}

void RealtimeAudioStreamer::cleanupRingBuffers() {
    if (inputRingBuffer != NULL) {
        vRingbufferDelete(inputRingBuffer);
        inputRingBuffer = NULL;
    }
    
    if (outputRingBuffer != NULL) {
        vRingbufferDelete(outputRingBuffer);
        outputRingBuffer = NULL;
    }
    
    Serial.println("🧹 Ring buffers cleaned up");
}

bool RealtimeAudioStreamer::writeToInputBuffer(const uint8_t* data, size_t size) {
    if (inputRingBuffer == NULL || data == nullptr || size == 0) {
        return false;
    }
    
    // Non-blocking write with timeout
    if (xRingbufferSend(inputRingBuffer, data, size, pdMS_TO_TICKS(10)) != pdTRUE) {
        metrics.chunksDropped++;
        return false;
    }
    
    return true;
}

size_t RealtimeAudioStreamer::readFromInputBuffer(uint8_t* data, size_t maxSize) {
    if (inputRingBuffer == NULL || data == nullptr || maxSize == 0) {
        return 0;
    }
    
    size_t itemSize = 0;
    uint8_t* item = (uint8_t*)xRingbufferReceive(inputRingBuffer, &itemSize, pdMS_TO_TICKS(1));
    
    if (item == NULL || itemSize == 0) {
        return 0;
    }
    
    // Copy data respecting maxSize limit
    size_t copySize = min(itemSize, maxSize);
    memcpy(data, item, copySize);
    
    // Return item to ring buffer
    vRingbufferReturnItem(inputRingBuffer, item);
    
    return copySize;
}

bool RealtimeAudioStreamer::isInputBufferEmpty() {
    if (inputRingBuffer == NULL) {
        return true;
    }
    
    UBaseType_t uxItemsWaiting = 0;
    vRingbufferGetInfo(inputRingBuffer, NULL, NULL, NULL, NULL, &uxItemsWaiting);
    return (uxItemsWaiting == 0);
}

size_t RealtimeAudioStreamer::getInputBufferFreeSpace() {
    if (inputRingBuffer == NULL) {
        return 0;
    }
    
    size_t freeSize = 0;
    vRingbufferGetInfo(inputRingBuffer, NULL, NULL, NULL, &freeSize, NULL);
    return freeSize;
}

// =============================================================================
// STREAMING CONTROL
// =============================================================================

bool RealtimeAudioStreamer::startStreaming() {
    if (!initialized) {
        Serial.println("❌ Real-time streamer not initialized");
        return false;
    }
    
    if (streaming) {
        Serial.println("⚠️ Already streaming");
        return true;
    }
    
    if (!isConnected) {
        Serial.println("❌ WebSocket not connected");
        return false;
    }
    
    Serial.println("🎤 Starting real-time audio streaming...");
    
    // Reset metrics
    resetMetrics();
    sequenceNumber = 0;
    streamingStartTime = millis();
    
    // Create streaming task
    BaseType_t result = xTaskCreate(
        audioStreamingTaskWrapper,
        "RTS_Task",
        STREAMING_TASK_STACK_SIZE,
        this,
        STREAMING_TASK_PRIORITY,
        &streamingTaskHandle
    );
    
    if (result != pdPASS) {
        Serial.println("❌ Failed to create streaming task");
        setState(RTS_ERROR);
        return false;
    }
    
    streaming = true;
    setState(RTS_STREAMING);
    
    // Visual feedback
    setLEDColor("cyan", 80);
    
    Serial.println("✅ Real-time streaming started");
    return true;
}

void RealtimeAudioStreamer::stopStreaming() {
    if (!streaming) {
        return;
    }
    
    Serial.println("🛑 Stopping real-time audio streaming...");
    setState(RTS_STOPPING);
    
    streaming = false;
    
    // Wait for task to finish
    if (streamingTaskHandle != NULL) {
        // Signal task to stop and wait
        uint32_t timeout = 0;
        while (eTaskGetState(streamingTaskHandle) != eDeleted && timeout < 5000) {
            delay(10);
            timeout += 10;
        }
        
        // Force delete if not finished
        if (eTaskGetState(streamingTaskHandle) != eDeleted) {
            vTaskDelete(streamingTaskHandle);
        }
        
        streamingTaskHandle = NULL;
    }
    
    // Clear visual feedback
    clearLEDs();
    
    setState(RTS_IDLE);
    
    Serial.println("✅ Real-time streaming stopped");
    printMetrics();
}

bool RealtimeAudioStreamer::isStreaming() {
    return streaming && (currentState == RTS_STREAMING || currentState == RTS_PAUSED_SILENCE);
}

// =============================================================================
// AUDIO STREAMING TASK IMPLEMENTATION
// =============================================================================

void RealtimeAudioStreamer::audioStreamingTaskWrapper(void* parameter) {
    RealtimeAudioStreamer* streamer = static_cast<RealtimeAudioStreamer*>(parameter);
    streamer->audioStreamingTask();
    vTaskDelete(NULL); // Self-delete when done
}

void RealtimeAudioStreamer::audioStreamingTask() {
    Serial.println("🎯 Audio streaming task started");
    
    uint8_t* chunkBuffer = (uint8_t*)malloc(networkState.currentChunkSize);
    if (chunkBuffer == nullptr) {
        Serial.println("❌ Failed to allocate chunk buffer in task");
        setState(RTS_ERROR);
        return;
    }
    
    uint32_t lastNetworkCheck = 0;
    uint32_t lastSilenceCheck __attribute__((unused)) = 0;
    uint32_t chunkStartTime = 0;
    
    while (streaming && currentState != RTS_STOPPING) {
        uint32_t currentTime = millis();
        
        // Update network conditions periodically
        if (currentTime - lastNetworkCheck > networkCheckInterval) {
            updateNetworkConditions();
            lastNetworkCheck = currentTime;
        }
        
        // Read audio data from I2S
        chunkStartTime = currentTime;
        uint8_t tempBuffer[BUFFER_SIZE];
        size_t bytesRead = readAudioData(tempBuffer, BUFFER_SIZE);
        
        if (bytesRead > 0) {
            // Write to ring buffer for continuous operation
            if (!writeToInputBuffer(tempBuffer, bytesRead)) {
                Serial.println("⚠️ Ring buffer full, dropping audio data");
                metrics.chunksDropped++;
            }
        }
        
        // Process accumulated data in chunks
        size_t availableData = readFromInputBuffer(chunkBuffer, networkState.currentChunkSize);
        
        if (availableData >= networkState.currentChunkSize || 
            (availableData > 0 && currentTime - lastChunkTime > latencyTarget)) {
            
            // Process the audio chunk
            processAudioChunk(chunkBuffer, availableData);
            
            // Apply real-time enhancements
            bool hasVoice = applyRealTimeEnhancements((int16_t*)chunkBuffer, availableData / 2);
            
            // Voice activity detection and adaptive streaming
            if (silenceDetectionEnabled) {
                if (hasVoice) {
                    handleVoicePeriod();
                } else {
                    handleSilencePeriod();
                }
            }
            
            // Send chunk if we have voice activity or silence detection is disabled
            if (hasVoice || !silenceDetectionEnabled || currentState != RTS_PAUSED_SILENCE) {
                sendAudioChunk(chunkBuffer, availableData);
                
                // Update performance metrics
                uint32_t chunkLatency = millis() - chunkStartTime;
                metrics.totalLatency += chunkLatency;
                metrics.averageLatency = metrics.totalLatency / max(1U, metrics.chunksProcessed);
                
                if (hasVoice) {
                    metrics.voiceChunks++;
                } else {
                    metrics.silenceChunks++;
                }
            }
            
            metrics.chunksProcessed++;
            lastChunkTime = currentTime;
            
            // Adaptive delay based on network conditions
            if (networkState.adaptiveDelay > 0) {
                vTaskDelay(pdMS_TO_TICKS(networkState.adaptiveDelay));
            }
        }
        
        // Update performance metrics periodically
        if (currentTime - lastPerformanceUpdate > 10000) { // Every 10 seconds
            updatePerformanceMetrics();
            lastPerformanceUpdate = currentTime;
        }
        
        // Small delay to prevent overwhelming the system
        vTaskDelay(pdMS_TO_TICKS(5));
        
        // Yield to other tasks
        taskYIELD();
    }
    
    free(chunkBuffer);
    Serial.println("🎯 Audio streaming task ended");
}

// =============================================================================
// AUDIO PROCESSING AND ENHANCEMENT
// =============================================================================

void RealtimeAudioStreamer::processAudioChunk(uint8_t* chunk, size_t size) {
    if (chunk == nullptr || size == 0) return;
    
    // Apply basic filtering and normalization
    int16_t* samples = (int16_t*)chunk;
    size_t sampleCount = size / 2;
    
    // Simple DC offset removal
    int32_t dcSum = 0;
    for (size_t i = 0; i < sampleCount; i++) {
        dcSum += samples[i];
    }
    int16_t dcOffset = dcSum / sampleCount;
    
    for (size_t i = 0; i < sampleCount; i++) {
        samples[i] -= dcOffset;
    }
}

bool RealtimeAudioStreamer::applyRealTimeEnhancements(int16_t* samples, size_t count) {
    if (samples == nullptr || count == 0) return false;
    
    // Fast Voice Activity Detection
    bool hasVoice = detectVoiceActivity(samples, count);
    
    // Apply AGC only during voice activity for efficiency
    if (hasVoice) {
        // Simple real-time AGC
        float currentRMS = calculateRMSLevel(samples, count);
        float targetGain = 1.0f;
        
        if (currentRMS > 0.01f) {
            targetGain = (float)AGC_TARGET_LEVEL / (currentRMS * 32768.0f);
            targetGain = constrain(targetGain, AGC_MIN_GAIN, AGC_MAX_GAIN);
        }
        
        // Smooth gain changes
        realtimeAGC.current_gain = realtimeAGC.current_gain * 0.9f + targetGain * 0.1f;
        
        // Apply gain
        for (size_t i = 0; i < count; i++) {
            float sample = (float)samples[i] * realtimeAGC.current_gain;
            samples[i] = (int16_t)constrain(sample, -32767, 32767);
        }
    }
    
    // Simple noise gate
    for (size_t i = 0; i < count; i++) {
        if (abs(samples[i]) < silenceThreshold) {
            samples[i] = (int16_t)(samples[i] * 0.1f);
        }
    }
    
    return hasVoice;
}

bool RealtimeAudioStreamer::detectVoiceActivity(int16_t* samples, size_t count) {
    if (samples == nullptr || count == 0) return false;
    
    // Calculate frame energy
    float energy = 0.0f;
    for (size_t i = 0; i < count; i++) {
        float sample = (float)samples[i] / 32768.0f;
        energy += sample * sample;
    }
    energy /= count;
    
    // Calculate zero crossing rate
    uint32_t crossings = 0;
    for (size_t i = 1; i < count; i++) {
        if ((samples[i] > 0 && samples[i-1] <= 0) || (samples[i] <= 0 && samples[i-1] > 0)) {
            crossings++;
        }
    }
    float zcr = (float)crossings / (count - 1);
    
    // Update real-time VAD metrics
    realTimeVAD.energy = energy;
    realTimeVAD.zero_crossing_rate = zcr;
    
    // Voice activity decision
    bool energyTest = energy > VAD_ENERGY_THRESHOLD / (32768.0f * 32768.0f);
    bool zcrTest = zcr > 0.05f && zcr < 0.5f;
    
    VADState newState = (energyTest && zcrTest) ? VAD_SPEECH : VAD_SILENCE;
    
    // Apply hysteresis
    if (realTimeVAD.state == VAD_SPEECH && newState == VAD_SILENCE) {
        if (realTimeVAD.silence_frames < 3) {
            newState = VAD_SPEECH;
        }
    } else if (realTimeVAD.state == VAD_SILENCE && newState == VAD_SPEECH) {
        if (realTimeVAD.speech_frames < 2) {
            newState = VAD_SILENCE;
        }
    }
    
    // Update frame counters
    if (newState == VAD_SPEECH) {
        realTimeVAD.speech_frames++;
        realTimeVAD.silence_frames = 0;
    } else {
        realTimeVAD.silence_frames++;
        realTimeVAD.speech_frames = 0;
    }
    
    realTimeVAD.state = newState;
    return (newState == VAD_SPEECH);
}

// =============================================================================
// NETWORK TRANSMISSION AND ADAPTATION
// =============================================================================

void RealtimeAudioStreamer::sendAudioChunk(uint8_t* chunk, size_t size) {
    if (chunk == nullptr || size == 0 || !isConnected) {
        return;
    }
    
    uint32_t transmissionStart = millis();
    
    // Calculate base64 output size
    unsigned int base64Length = calculateBase64EncodedSize(size);
    unsigned char* base64Output = new unsigned char[base64Length + 1];
    
    if (base64Output == nullptr) {
        Serial.println("❌ Failed to allocate base64 buffer");
        metrics.chunksDropped++;
        return;
    }
    
    // Encode to base64
    unsigned int encodedLength = encodeBase64(chunk, size, base64Output, base64Length + 1);
    if (encodedLength == 0) {
        Serial.println("❌ Base64 encoding failed");
        delete[] base64Output;
        metrics.chunksDropped++;
        return;
    }
    
    base64Output[encodedLength] = '\0';
    String base64Chunk = String((char*)base64Output);
    delete[] base64Output;
    
    // Create WebSocket message
    DynamicJsonDocument doc(1024 + base64Chunk.length());
    doc["type"] = "realtime_audio_chunk";
    doc["device_id"] = getCurrentDeviceId();
    doc["timestamp"] = millis();
    doc["sequence"] = sequenceNumber++;
    doc["chunk_size"] = size;
    doc["format"] = "pcm_s16le";
    doc["sample_rate"] = sampleRate;
    doc["channels"] = 1;
    doc["has_voice"] = (realTimeVAD.state == VAD_SPEECH);
    doc["chunk_latency"] = millis() - transmissionStart;
    doc["audio_data"] = base64Chunk;
    
    String message;
    serializeJson(doc, message);
    
    // Send with error handling
    if (webSocket.sendTXT(message)) {
        metrics.chunksSent++;
        networkState.consecutiveFailures = 0;
        
        // Adaptive chunk size increase on success
        if (networkState.canIncreaseChunkSize && 
            metrics.chunksSent % 10 == 0 && 
            networkState.consecutiveFailures == 0) {
            adjustChunkSize(true);
        }
    } else {
        metrics.chunksDropped++;
        networkState.consecutiveFailures++;
        
        Serial.printf("❌ Failed to send audio chunk %d\n", sequenceNumber - 1);
        
        // Adjust chunk size down on failures
        if (networkState.consecutiveFailures >= RTS_CHUNK_ADJUSTMENT_THRESHOLD) {
            adjustChunkSize(false);
            networkState.consecutiveFailures = 0; // Reset after adjustment
        }
    }
    
    // Update average chunk size metric
    metrics.averageChunkSize = (metrics.averageChunkSize * (metrics.chunksSent - 1) + size) / 
                               max(1U, metrics.chunksSent);
}

void RealtimeAudioStreamer::updateNetworkConditions() {
    int32_t currentRSSI = WiFi.RSSI();
    networkState.currentRSSI = currentRSSI;
    
    NetworkCondition newCondition;
    if (currentRSSI > RTS_GOOD_NETWORK_RSSI) {
        newCondition = NETWORK_EXCELLENT;
    } else if (currentRSSI > RTS_FAIR_NETWORK_RSSI) {
        newCondition = NETWORK_GOOD;
    } else if (currentRSSI > -80) {
        newCondition = NETWORK_FAIR;
    } else {
        newCondition = NETWORK_POOR;
    }
    
    if (newCondition != networkState.condition) {
        networkState.condition = newCondition;
        adjustForNetworkConditions();
        
        Serial.printf("📡 Network condition changed to: %s (RSSI: %d dBm)\n", 
                      newCondition == NETWORK_EXCELLENT ? "EXCELLENT" :
                      newCondition == NETWORK_GOOD ? "GOOD" :
                      newCondition == NETWORK_FAIR ? "FAIR" : "POOR", 
                      currentRSSI);
    }
}

void RealtimeAudioStreamer::adjustForNetworkConditions() {
    switch (networkState.condition) {
        case NETWORK_EXCELLENT:
            networkState.adaptiveDelay = 5;
            networkState.canIncreaseChunkSize = true;
            if (networkState.currentChunkSize < RTS_MAX_CHUNK_SIZE) {
                adjustChunkSize(true);
            }
            break;
            
        case NETWORK_GOOD:
            networkState.adaptiveDelay = 10;
            networkState.canIncreaseChunkSize = true;
            break;
            
        case NETWORK_FAIR:
            networkState.adaptiveDelay = 20;
            networkState.canIncreaseChunkSize = false;
            if (networkState.currentChunkSize > RTS_CHUNK_SIZE) {
                adjustChunkSize(false);
            }
            break;
            
        case NETWORK_POOR:
            networkState.adaptiveDelay = 50;
            networkState.canIncreaseChunkSize = false;
            if (networkState.currentChunkSize > RTS_MIN_CHUNK_SIZE) {
                adjustChunkSize(false);
            }
            break;
    }
}

size_t RealtimeAudioStreamer::getOptimalChunkSize() {
    return networkState.currentChunkSize;
}

void RealtimeAudioStreamer::adjustChunkSize(bool increase) {
    size_t oldSize = networkState.currentChunkSize;
    
    if (increase && networkState.canIncreaseChunkSize) {
        networkState.currentChunkSize = min(
            (size_t)(networkState.currentChunkSize * 1.25), 
            (size_t)RTS_MAX_CHUNK_SIZE
        );
    } else if (!increase) {
        networkState.currentChunkSize = max(
            (size_t)(networkState.currentChunkSize * 0.75), 
            (size_t)RTS_MIN_CHUNK_SIZE
        );
    }
    
    if (oldSize != networkState.currentChunkSize) {
        Serial.printf("📊 Chunk size adjusted: %d -> %d bytes\n", oldSize, networkState.currentChunkSize);
    }
}

// =============================================================================
// SILENCE DETECTION AND ADAPTIVE STREAMING
// =============================================================================

void RealtimeAudioStreamer::handleVoicePeriod() {
    lastVoiceActivity = millis();
    continuousSilenceTime = 0;
    
    if (currentState == RTS_PAUSED_SILENCE) {
        Serial.println("🎤 Voice detected, resuming streaming");
        setState(RTS_STREAMING);
        setLEDColor("cyan", 80);
    }
}

void RealtimeAudioStreamer::handleSilencePeriod() {
    uint32_t currentTime = millis();
    
    if (lastVoiceActivity > 0) {
        continuousSilenceTime = currentTime - lastVoiceActivity;
        
        if (continuousSilenceTime > RTS_CONTINUOUS_SILENCE_LIMIT && 
            currentState == RTS_STREAMING) {
            Serial.println("🔇 Extended silence detected, pausing transmission");
            setState(RTS_PAUSED_SILENCE);
            setLEDColor("blue", 30);
        }
    }
}

bool RealtimeAudioStreamer::isCurrentlySilent() {
    return (realTimeVAD.state == VAD_SILENCE) || 
           (continuousSilenceTime > RTS_CONTINUOUS_SILENCE_LIMIT);
}

// =============================================================================
// SERVER AUDIO RESPONSE HANDLING
// =============================================================================

void RealtimeAudioStreamer::processIncomingAudio(uint8_t* audioData, size_t length) {
    if (audioData == nullptr || length == 0 || outputRingBuffer == NULL) {
        return;
    }
    
    // Write to output ring buffer for playback
    if (xRingbufferSend(outputRingBuffer, audioData, length, pdMS_TO_TICKS(10)) != pdTRUE) {
        Serial.println("⚠️ Output buffer full, dropping server audio");
        return;
    }
    
    // Trigger immediate playback
    handleServerAudioResponse(audioData, length);
}

void RealtimeAudioStreamer::handleServerAudioResponse(uint8_t* audioData, size_t length) {
    if (audioData == nullptr || length == 0) {
        return;
    }
    
    Serial.printf("🔊 Received real-time audio response: %d bytes\n", length);
    
    // Temporarily pause streaming to avoid echo
    bool wasStreaming = streaming;
    if (wasStreaming) {
        setState(RTS_PAUSED_SILENCE);
    }
    
    // Play the audio response
    playAudioResponse(audioData, length);
    
    // Resume streaming after a short delay
    if (wasStreaming) {
        delay(100); // Brief pause to avoid echo
        setState(RTS_STREAMING);
    }
}

// =============================================================================
// PERFORMANCE METRICS AND MONITORING
// =============================================================================

void RealtimeAudioStreamer::resetMetrics() {
    memset(&metrics, 0, sizeof(RTSMetrics));
    metrics.lastMetricsReset = millis();
}

void RealtimeAudioStreamer::updatePerformanceMetrics() {
    uint32_t currentTime = millis();
    uint32_t uptime = currentTime - streamingStartTime;
    
    if (uptime > 0 && metrics.chunksProcessed > 0) {
        // Calculate throughput
        float chunksPerSecond = (float)metrics.chunksProcessed / (uptime / 1000.0f);
        float avgLatency = (float)metrics.totalLatency / metrics.chunksProcessed;
        
        // Log performance summary
        if (metrics.chunksProcessed % 100 == 0) { // Every 100 chunks
            Serial.printf("📊 Performance: %.1f chunks/sec, Avg Latency: %.1fms, Drops: %d\n",
                          chunksPerSecond, avgLatency, metrics.chunksDropped);
        }
    }
}

void RealtimeAudioStreamer::printMetrics() {
    uint32_t uptime = millis() - streamingStartTime;
    float uptimeSeconds = uptime / 1000.0f;
    
    Serial.println("=== 🎤 Real-time Audio Streaming Metrics ===");
    Serial.printf("Streaming Uptime: %.1f seconds\n", uptimeSeconds);
    Serial.printf("Chunks Processed: %d\n", metrics.chunksProcessed);
    Serial.printf("Chunks Sent: %d\n", metrics.chunksSent);
    Serial.printf("Chunks Dropped: %d\n", metrics.chunksDropped);
    Serial.printf("Success Rate: %.1f%%\n", 
                  metrics.chunksProcessed > 0 ? 
                  (float)metrics.chunksSent / metrics.chunksProcessed * 100.0f : 0.0f);
    Serial.printf("Voice Chunks: %d (%.1f%%)\n", metrics.voiceChunks,
                  metrics.chunksProcessed > 0 ?
                  (float)metrics.voiceChunks / metrics.chunksProcessed * 100.0f : 0.0f);
    Serial.printf("Silence Chunks: %d (%.1f%%)\n", metrics.silenceChunks,
                  metrics.chunksProcessed > 0 ?
                  (float)metrics.silenceChunks / metrics.chunksProcessed * 100.0f : 0.0f);
    Serial.printf("Average Latency: %d ms\n", metrics.averageLatency);
    Serial.printf("Average Chunk Size: %.0f bytes\n", metrics.averageChunkSize);
    Serial.printf("Current Chunk Size: %d bytes\n", networkState.currentChunkSize);
    Serial.printf("Network Condition: %s\n", 
                  networkState.condition == NETWORK_EXCELLENT ? "EXCELLENT" :
                  networkState.condition == NETWORK_GOOD ? "GOOD" :
                  networkState.condition == NETWORK_FAIR ? "FAIR" : "POOR");
    Serial.printf("Network RSSI: %d dBm\n", networkState.currentRSSI);
    Serial.printf("Consecutive Failures: %d\n", networkState.consecutiveFailures);
    Serial.printf("Current State: %s\n", 
                  currentState == RTS_IDLE ? "IDLE" :
                  currentState == RTS_STREAMING ? "STREAMING" :
                  currentState == RTS_PAUSED_SILENCE ? "PAUSED_SILENCE" : "OTHER");
    Serial.println("=============================================");
}

// =============================================================================
// STATE MANAGEMENT
// =============================================================================

void RealtimeAudioStreamer::setState(RTSState newState) {
    if (stateMutex != NULL) {
        xSemaphoreTake(stateMutex, portMAX_DELAY);
    }
    
    if (currentState != newState) {
        RTSState oldState = currentState;
        currentState = newState;
        
        const char* stateNames[] = {"IDLE", "INITIALIZING", "STREAMING", "PAUSED_SILENCE", "ERROR", "STOPPING"};
        Serial.printf("🎵 RTS State: %s -> %s\n", 
                      stateNames[oldState], stateNames[newState]);
    }
    
    if (stateMutex != NULL) {
        xSemaphoreGive(stateMutex);
    }
}

// =============================================================================
// CLEANUP AND ERROR HANDLING
// =============================================================================

void RealtimeAudioStreamer::cleanup() {
    Serial.println("🧹 Cleaning up Real-time Audio Streamer...");
    
    // Stop streaming if active
    if (streaming) {
        stopStreaming();
    }
    
    // Clean up FreeRTOS resources
    if (audioQueue != NULL) {
        vQueueDelete(audioQueue);
        audioQueue = NULL;
    }
    
    if (stateMutex != NULL) {
        vSemaphoreDelete(stateMutex);
        stateMutex = NULL;
    }
    
    // Clean up ring buffers
    cleanupRingBuffers();
    
    // Free memory buffers
    if (processingBuffer != nullptr) {
        free(processingBuffer);
        processingBuffer = nullptr;
    }
    
    initialized = false;
    setState(RTS_IDLE);
    
    Serial.println("✅ Real-time Audio Streamer cleanup completed");
}

// =============================================================================
// C-STYLE WRAPPER FUNCTIONS
// =============================================================================

extern "C" {
    bool initRealtimeStreaming() {
        return realtimeStreamer.init();
    }
    
    bool startRealtimeStreaming() {
        return realtimeStreamer.startStreaming();
    }
    
    void stopRealtimeStreaming() {
        realtimeStreamer.stopStreaming();
    }
    
    bool isRealtimeStreaming() {
        return realtimeStreamer.isStreaming();
    }
    
    void processIncomingRealtimeAudio(uint8_t* audioData, size_t length) {
        realtimeStreamer.processIncomingAudio(audioData, length);
    }
    
    void printRealtimeStreamingMetrics() {
        realtimeStreamer.printMetrics();
    }
    
    void cleanupRealtimeStreaming() {
        realtimeStreamer.cleanup();
    }
}

// =============================================================================
// PERFORMANCE MONITORING INTEGRATION
// =============================================================================


void updateStreamingQualityScore(float score) {
    // Integration point for quality monitoring
    // Could be used to adjust streaming parameters based on perceived quality
    if (score < 70.0f) {
        Serial.printf("⚠️ Low streaming quality score: %.1f%%\n", score);
    }
}

void onNetworkConditionChanged(NetworkCondition newCondition) {
    // Callback for external network monitoring integration
    Serial.printf("📡 External network condition update: %d\n", newCondition);
}