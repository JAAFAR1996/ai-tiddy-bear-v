#include "audio_handler.h"
#include "config.h"
#include "feature_config.h"
#include "websocket_handler.h"
#include "hardware.h"
#include "monitoring.h"
#include "system_monitor.h"  // For production system monitoring
#include "comprehensive_logging.h"  // Comprehensive logging system
#include <driver/adc.h>       // ADC for analog microphone (HW-164)
#include <WiFi.h>
#include <math.h>
#include <esp_task_wdt.h>  // For watchdog reset
#include <driver/dac.h>    // ESP32 WROOM Ã™Å Ã˜Â¯Ã˜Â¹Ã™â€¦ DAC Ã˜Â¨Ã˜Â´Ã™Æ'Ã™â€ž Ã™Æ'Ã˜Â§Ã™â€¦Ã™â€ž
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/ringbuf.h"
#include <driver/i2s.h>
#include <esp_heap_caps.h>
#if AUDIO_USE_DAC
#include <driver/dac.h>
#endif
  
// Production FreeRTOS priorities for audio
#define AUDIO_CAPTURE_PRIORITY   (configMAX_PRIORITIES - 2)  // Highest for audio capture
#define AUDIO_PLAYBACK_PRIORITY  (configMAX_PRIORITIES - 3)  // High for audio playback  
#define WEBSOCKET_SEND_PRIORITY  (configMAX_PRIORITIES - 4)  // Medium for network

// Reduced ring buffer sizes to prevent memory fragmentation
#define CAPTURE_RING_BYTES      (16 * 1024)  // 16KB for capture (reduced)
#define PLAYBACK_RING_BYTES     (16 * 1024)  // 16KB for playback (reduced)

AudioState currentAudioState = AUDIO_IDLE;
// Safe memory management with RAII pattern
static uint8_t* audioBuffer = nullptr;
size_t audioBufferSize = 0;
size_t audioBufferIndex = 0;
bool recordingActive = false;
volatile bool audioInitialized = false;

// Ã¢Å"â€¦ Ã™â€¦Ã˜ÂªÃ˜ÂºÃ™Å Ã˜Â±Ã˜Â§Ã˜Âª Ã™â€žÃ™â€žÃ™â‚¬ streaming - Ã˜Â¥Ã˜ÂµÃ™â€žÃ˜Â§Ã˜Â­ Ã˜Â®Ã˜Â·Ã˜Â£ Ã˜Â§Ã™â€žÃ˜ÂªÃ˜Â¬Ã™â€¦Ã™Å Ã˜Â¹
static unsigned long recordingStartTime = 0;
static size_t bufferReadPos = 0;
static size_t bufferWritePos = 0;
static size_t audioSamplesRecorded = 0;

// Audio enhancement global state
NoiseProfile noiseProfile{};
AGCState agcState{};
VADMetrics vadMetrics{};

// Enhanced audio processing buffers
static int16_t* processingBuffer = nullptr;
static float* fftBuffer = nullptr;
static bool enhancementsInitialized = false;

// I2S and task management
static bool i2s0_installed = false;
static TaskHandle_t hPlaybackTask = nullptr;
static TaskHandle_t hCaptureTask = nullptr;
static uint8_t* capture_rb = nullptr;
static uint8_t* playback_rb = nullptr;

// PAM8403 Audio System Variables - using config.h definitions
static int masterVolume = 50;    // Master volume 0-100
static bool dacInitialized = false;

// Ã¢Å"â€¦ I2S and RingBuffer variables (Global/Static)
static SemaphoreHandle_t i2s_mutex = nullptr;
static RingbufHandle_t   audio_capture_ringbuf = nullptr;
static RingbufHandle_t   audio_playback_ringbuf = nullptr;
static TaskHandle_t      audio_capture_task_handle = nullptr;
static TaskHandle_t      audio_playback_task_handle = nullptr;
static TaskHandle_t      websocket_send_task_handle = nullptr;
static volatile bool     i2s_tasks_running = false;

// Analog microphone (amplified) streaming
static volatile bool     streamingActive = false;
static int               adcBaseline = 2048; // DC offset for 12-bit ADC
static adc1_channel_t    micChannel = ADC1_CHANNEL_6; // Default for GPIO34

// Forward declaration to send over WebSocket JSON protocol
extern void sendAudioDataWebSocket(uint8_t* audioData, size_t length);

// Map MIC_PIN to ADC1 channel (GPIOs valid for ADC1)
static adc1_channel_t pinToAdc1Channel(int pin) {
  switch (pin) {
    case 36: return ADC1_CHANNEL_0; // VP
    case 37: return ADC1_CHANNEL_1; // VN (usually internal)
    case 38: return ADC1_CHANNEL_2; // sensVN (usually internal)
    case 39: return ADC1_CHANNEL_3; // VN
    case 32: return ADC1_CHANNEL_4;
    case 33: return ADC1_CHANNEL_5;
    case 34: return ADC1_CHANNEL_6;
    case 35: return ADC1_CHANNEL_7;
    default: return ADC1_CHANNEL_6; // Fallback to GPIO34
  }
}

static void adc_calibrate_baseline() {
  // Estimate DC baseline from a short sample window
  const int N = 512;
  uint32_t sum = 0;
  for (int i = 0; i < N; ++i) {
    sum += adc1_get_raw(micChannel);
    ets_delay_us(50);
  }
  adcBaseline = (int)(sum / N);
}

static void adc_capture_task(void* pv) {
  const uint32_t target_us = 1000000UL / SAMPLE_RATE; // ~62.5us at 16kHz
  static uint8_t chunkBuf[AUDIO_CHUNK_SIZE];
  size_t index = 0;
  const size_t bytesPerSample = 2;

  // Calibrate baseline at task start
  adc_calibrate_baseline();

  while (streamingActive) {
    uint32_t raw = (uint32_t)adc1_get_raw(micChannel); // 0..4095
    // Slow moving average to track DC drift
    adcBaseline = (adcBaseline * 99 + (int)raw) / 100;
    int32_t centered = (int32_t)raw - (int32_t)adcBaseline; // center around 0
    // Scale 12-bit centered sample to 16-bit signed range
    int32_t s32 = centered << 4; // 12 -> 16 bits
    if (s32 > 32767) s32 = 32767; if (s32 < -32768) s32 = -32768;
    int16_t s16 = (int16_t)s32;

    // Little-endian PCM 16-bit
    chunkBuf[index++] = (uint8_t)(s16 & 0xFF);
    chunkBuf[index++] = (uint8_t)((s16 >> 8) & 0xFF);

    if (index >= AUDIO_CHUNK_SIZE) {
      sendAudioData(chunkBuf, index);
      index = 0;
    }

    // Pace to target sample rate
    ets_delay_us(target_us);
    taskYIELD();
  }

  // Flush any remaining samples
  if (index > 0) {
    sendAudioData(chunkBuf, index);
  }

  // Mark handle as cleared before self-delete to avoid double delete
  audio_capture_task_handle = nullptr;
  vTaskDelete(NULL);
}

// Memory management functions
static bool allocateAudioBuffer() {
  if (audioBuffer != nullptr) {
    free(audioBuffer);
    audioBuffer = nullptr;
  }
  
  {
    size_t target = SAMPLE_RATE * RECORD_TIME * 2; // 16-bit samples
    // Limit buffer temporarily to reduce TLS pressure during handshake
    const size_t AUDIO_BUFFER_BYTES = 48000; // temporary cap
    audioBufferSize = (target > AUDIO_BUFFER_BYTES) ? AUDIO_BUFFER_BYTES : target;
  }
  audioBuffer = (uint8_t*)malloc(audioBufferSize);
  
  if (audioBuffer == nullptr) {
    Serial.println("Ã¢Â'Å' Failed to allocate audio buffer!");
    audioBufferSize = 0;
    setAudioState(AUDIO_ERROR);
    return false;
  }
  
  Serial.printf("Audio buffer allocated: %d bytes\n", audioBufferSize);
  return true;
}

static void deallocateAudioBuffer() {
  if (audioBuffer != nullptr) {
    free(audioBuffer);
    audioBuffer = nullptr;
  }
  audioBufferSize = 0;
  audioBufferIndex = 0;
}

bool initAudio() {
  if (audioInitialized) {
    Serial.println("Audio already initialized");
    return true;
  }
  
  Serial.println("Initializing audio system...");
  
  // Allocate main audio buffer
  if (!allocateAudioBuffer()) {
    return false;
  }
  
  // Initialize analog microphone ADC configuration
  pinMode(MIC_PIN, INPUT);
  micChannel = pinToAdc1Channel(MIC_PIN);
  adc1_config_width(ADC_WIDTH_BIT_12);
  adc1_config_channel_atten(micChannel, ADC_ATTEN_DB_12); // Use non-deprecated 0-3.3V equivalent
  
  // I2S not used for mic: using ADC sampling (amplified mic on analog pin)
  Serial.println("Analog mic via ADC configured (I2S not used)");
  
  // Initialize audio enhancements (stub)
  Serial.println("Audio enhancements initialization stub - not implemented");
  
  audioInitialized = true;
  setAudioState(AUDIO_IDLE);
  
  Serial.println("Audio system initialized successfully");
  return true;
}

void cleanupAudio() {
  if (!audioInitialized) return;
  
  Serial.println("Cleaning up audio system...");
  
  // Stop streaming task if active
  if (streamingActive) {
    streamingActive = false;
    // Wait for capture task to exit on its own (max ~500ms)
    const int maxWaitIters = 50;
    int iters = 0;
    while (audio_capture_task_handle != nullptr && iters++ < maxWaitIters) {
      vTaskDelay(10 / portTICK_PERIOD_MS);
      taskYIELD();
    }
  }

  // Stop any active recording
  if (recordingActive) {
    stopRecording();
  }
  
  // Cleanup I2S
  if (i2s0_installed) {
    i2s_driver_uninstall(I2S_NUM_0);
    i2s0_installed = false;
  }
  
  // Cleanup tasks
  if (hCaptureTask) {
    vTaskDelete(hCaptureTask);
    hCaptureTask = nullptr;
  }
  if (hPlaybackTask) {
    vTaskDelete(hPlaybackTask);
    hPlaybackTask = nullptr;
  }
  
  // Cleanup ring buffers
  if (audio_capture_ringbuf) {
    vRingbufferDelete(audio_capture_ringbuf);
    audio_capture_ringbuf = nullptr;
  }
  if (audio_playback_ringbuf) {
    vRingbufferDelete(audio_playback_ringbuf);
    audio_playback_ringbuf = nullptr;
  }
  
  // Cleanup mutex
  if (i2s_mutex) {
    vSemaphoreDelete(i2s_mutex);
    i2s_mutex = nullptr;
  }
  
  // Free processing buffers
  if (processingBuffer) {
    free(processingBuffer);
    processingBuffer = nullptr;
  }
  if (fftBuffer) {
    free(fftBuffer);
    fftBuffer = nullptr;
  }
  
  // Free main audio buffer
  deallocateAudioBuffer();
  
  audioInitialized = false;
  setAudioState(AUDIO_IDLE);
  
  Serial.println("Audio system cleaned up");
}

void startRecording() {
  if (!audioInitialized) {
    Serial.println("Audio not initialized");
    return;
  }
  
  if (recordingActive) {
    Serial.println("Already recording");
    return;
  }
  
  Serial.println("Starting audio recording...");
  
  audioBufferIndex = 0;
  recordingStartTime = millis();
  recordingActive = true;
  setAudioState(AUDIO_RECORDING);
  
  Serial.println("Audio recording started");
}

void stopRecording() {
  if (!recordingActive) {
    Serial.println("Not currently recording");
    return;
  }
  
  Serial.println("Stopping audio recording...");
  
  recordingActive = false;
  setAudioState(AUDIO_IDLE);
  
  unsigned long recordingDuration = millis() - recordingStartTime;
  Serial.printf("Recording stopped. Duration: %lu ms, Samples: %d\n", 
                recordingDuration, audioBufferIndex / 2);
}

void playAudioResponse(uint8_t* audioData, size_t length) {
  if (!audioData || length < 2) {
    logAudioEvent("Audio playback skipped", "No data");
    updateAudioFlowState(AUDIO_FLOW_COMPLETE);
    return;
  }
  logAudioEvent("Audio playback started", "PCM s16le via DAC (if enabled)");
#if AUDIO_USE_DAC
  // Play PCM s16le mono at SAMPLE_RATE using 8-bit DAC on GPIO25
  const int16_t* samples = reinterpret_cast<const int16_t*>(audioData);
  size_t numSamples = length / 2;
  const uint32_t us_per_sample = 1000000UL / SAMPLE_RATE; // ~62us at 16kHz
  dacOutputEnable(DAC_CHANNEL_1); // GPIO25
  for (size_t i = 0; i < numSamples; ++i) {
    int16_t s = samples[i];
    // Map 16-bit signed to 8-bit unsigned for DAC: center 0 -> 128
    uint8_t v = static_cast<uint8_t>((s >> 8) + 128);
    dacWrite(AUDIO_OUT_LEFT, v);
    ets_delay_us(us_per_sample);
    if ((i & 0x3FF) == 0) yield();
  }
  dacWrite(AUDIO_OUT_LEFT, 128);
  dacOutputDisable(DAC_CHANNEL_1);
  logAudioPlayback("response", 70, (int)((numSamples * 1000UL) / SAMPLE_RATE), true);
#else
  // PWM/I2S not implemented for streaming playback in this build
  (void)audioData; (void)length;
  logAudioEvent("Audio playback skipped", "AUDIO_USE_DAC=0");
#endif
  updateAudioFlowState(AUDIO_FLOW_COMPLETE);
}

void startRealTimeStreaming() {
  if (streamingActive) {
    Serial.println("Already streaming");
    return;
  }
  if (!audioInitialized) {
    if (!initAudio()) {
      Serial.println("Failed to init audio for streaming");
      return;
    }
  }
  streamingActive = true;
  setAudioState(AUDIO_STREAMING);
  updateAudioFlowState(AUDIO_FLOW_RECORDING);
  logAudioEvent("Real-time streaming started", "ADC 16kHz mono s16le");

  // Notify server: start audio session
  sendAudioStartSession();

  // Spawn high-priority capture task
  if (audio_capture_task_handle) {
    vTaskDelete(audio_capture_task_handle);
    audio_capture_task_handle = nullptr;
  }
  xTaskCreatePinnedToCore(
    adc_capture_task,
    "adc_capture_task",
    4096,
    nullptr,
    AUDIO_CAPTURE_PRIORITY,
    &audio_capture_task_handle,
    0
  );
  logCompleteAudioFlow("START", "SUCCESS", "Streaming task launched");
}

void stopRealTimeStreaming() {
  if (!streamingActive) {
    return;
  }
  // Mark next outgoing chunk as final, then stop capture loop
  markNextChunkFinal();
  streamingActive = false;
  // Wait for capture task to exit on its own (max ~500ms)
  const int maxWaitIters = 50;
  int iters = 0;
  while (audio_capture_task_handle != nullptr && iters++ < maxWaitIters) {
    vTaskDelay(10 / portTICK_PERIOD_MS);
    taskYIELD();
  }
  // Notify server: end audio session
  sendAudioEndSession();
  setAudioState(AUDIO_IDLE);
  updateAudioFlowState(AUDIO_FLOW_COMPLETE);
  logAudioEvent("Real-time streaming stopped", "ADC capture ended");
  logCompleteAudioFlow("STOP", "SUCCESS", "Streaming terminated");
}

void sendAudioToServer() {
  if (!isConnected || audioBufferIndex == 0 || audioBuffer == nullptr) {
    Serial.println("Ã¢Å¡Â Ã¯Â¸Â Cannot send audio: not connected or no data");
    return;
  }
  
  Serial.println("Ã°Å¸â€œÂ¤ Sending audio to server...");

  // Send audio data via WebSocket
  sendAudioData(audioBuffer, audioBufferIndex);
  
  // Reset buffer after sending
  audioBufferIndex = 0;
  
  Serial.println("Audio sent to server successfully");
}

void setAudioState(AudioState state) {
  if (currentAudioState != state) {
    currentAudioState = state;
    logAudioEvent("Audio state changed", "New state: " + String(state));
  }
}

AudioState getAudioState() {
  return currentAudioState;
}

bool isRecording() {
  return recordingActive;
}

void sendAudioData(uint8_t* audioData, size_t length) {
  if (!audioData || length == 0) return;
  // Forward to WebSocket sender (JSON + Base64 with HMAC)
  sendAudioDataWebSocket(audioData, length);
}

void handleAudioResponse(JsonObject params) {
  logAudioEvent("Handling audio response", "Simple implementation");
  
  String text = params["text"] | "";
  String format = params["format"] | "pcm_s16le";
  int audioRate = params["audio_rate"] | 22050;
  
  logAudioEvent("Audio response received", "Text: " + text + ", Format: " + format + ", Rate: " + String(audioRate));
  
  // Simulate audio playback
  playAudioResponse(nullptr, 0);
}

String calculateAudioHMAC(uint8_t* audioData, size_t length, const String& chunkId, const String& sessionId) {
  logAudioEvent("Calculating audio HMAC", "Length: " + String(length));
  
  // Simple HMAC simulation
  String hmac = "simulated_hmac_" + String(millis());
  
  logAudioEvent("Audio HMAC calculated", "HMAC: " + hmac.substring(0, 16) + "...");
  
  return hmac;
}

// Stub functions for compatibility
bool setupI2S() {
  Serial.println("I2S setup stub - not implemented");
  return true;
}

void initAudioEnhancements() {
  Serial.println("Audio enhancements initialization stub - not implemented");
}

// Additional stub functions
uint8_t* compressAudioData(uint8_t* data, size_t length, size_t* compressedSize) {
  *compressedSize = length;
  return data;
}

size_t readAudioData(uint8_t* buffer, size_t bufferSize) {
  return 0;
}

void printAudioInfo() {
  Serial.println("Audio Info: Stub implementation");
}

void printAudioEnhancementStats() {
  Serial.println("Audio Enhancement Stats: Stub implementation");
}

// Play tone function for button feedback
void playTone(int frequency, int duration) {
  logAudioEvent("Playing tone", "Frequency: " + String(frequency) + " Hz, Duration: " + String(duration) + " ms");
  // Simple tone simulation - in real implementation, use ESP32 tone() or I2S
  Serial.printf("Playing tone: %d Hz for %d ms\n", frequency, duration);
  delay(duration);
  logAudioEvent("Tone playback complete", "");
}
