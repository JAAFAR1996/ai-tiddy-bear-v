#include "audio_handler.h"
#include "websocket_handler.h"
#include "hardware.h"
#include <WiFi.h>

AudioState currentAudioState = AUDIO_IDLE;
// Reduced buffer size: 3 seconds * 16kHz * 2 bytes = 96KB -> use smaller chunks
static uint8_t* audioBuffer = nullptr;
size_t audioBufferSize = 0;
size_t audioBufferIndex = 0;
bool recordingActive = false;

void initAudio() {
  Serial.println("🎤 Initializing audio...");
  
  // Allocate audio buffer dynamically (smaller size)
  audioBufferSize = SAMPLE_RATE * RECORD_TIME * 2; // 16-bit samples
  audioBuffer = (uint8_t*)malloc(audioBufferSize);
  
  if (audioBuffer == nullptr) {
    Serial.println("❌ Failed to allocate audio buffer!");
    audioBufferSize = 0;
    return;
  }
  
  setupI2S();
  currentAudioState = AUDIO_IDLE;
  
  Serial.printf("✅ Audio initialized! Buffer: %d bytes\n", audioBufferSize);
}

void setupI2S() {
  // I2S configuration for microphone input
  i2s_config_t i2s_config_in = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = BUFFER_SIZE,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  // I2S pin configuration for input
  i2s_pin_config_t pin_config_in = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };

  // Install and start I2S driver
  i2s_driver_install(I2S_NUM_0, &i2s_config_in, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config_in);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

void startRecording() {
  if (currentAudioState != AUDIO_IDLE || audioBuffer == nullptr) {
    Serial.println("⚠️ Audio busy or buffer not available, cannot start recording");
    return;
  }
  
  Serial.println("🎤 Starting audio recording...");
  
  // Reset buffer
  audioBufferIndex = 0;
  memset(audioBuffer, 0, audioBufferSize);
  
  // Set state
  setAudioState(AUDIO_RECORDING);
  recordingActive = true;
  
  // Visual feedback
  setLEDColor("blue", 100);
  
  // Record for specified time
  unsigned long startTime = millis();
  size_t bytesRead = 0;
  
  while (millis() - startTime < RECORD_TIME * 1000 && recordingActive) {
    uint8_t tempBuffer[BUFFER_SIZE];
    size_t bytesToRead = min((size_t)BUFFER_SIZE, audioBufferSize - audioBufferIndex);
    
    if (bytesToRead > 0) {
      bytesRead = readAudioData(tempBuffer, bytesToRead);
      
      if (bytesRead > 0) {
        memcpy(audioBuffer + audioBufferIndex, tempBuffer, bytesRead);
        audioBufferIndex += bytesRead;
      }
    }
    
    delay(10);
  }
  
  stopRecording();
  
  Serial.printf("🎤 Recording complete: %d bytes\n", audioBufferIndex);
  
  // Send to server
  if (audioBufferIndex > 0) {
    sendAudioToServer();
  }
}

void stopRecording() {
  if (currentAudioState != AUDIO_RECORDING) {
    return;
  }
  
  recordingActive = false;
  setAudioState(AUDIO_IDLE);
  
  // Clear visual feedback
  clearLEDs();
  
  Serial.println("🎤 Recording stopped");
}

bool isRecording() {
  return currentAudioState == AUDIO_RECORDING;
}

void playAudioResponse(uint8_t* audioData, size_t length) {
  if (currentAudioState != AUDIO_IDLE) {
    Serial.println("⚠️ Audio busy, cannot play response");
    return;
  }
  
  Serial.printf("🔊 Playing audio response: %d bytes\n", length);
  
  setAudioState(AUDIO_PLAYING);
  
  // Visual feedback
  setLEDColor("green", 100);
  
  // Configure I2S for output
  i2s_config_t i2s_config_out = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = BUFFER_SIZE,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config_out = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = SPEAKER_PIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  // Reconfigure for output
  i2s_driver_uninstall(I2S_NUM_0);
  i2s_driver_install(I2S_NUM_0, &i2s_config_out, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config_out);
  
  // Play audio data
  writeAudioData(audioData, length);
  
  // Wait for playback to complete
  delay(length * 1000 / (SAMPLE_RATE * 2)); // Approximate duration
  
  // Reconfigure back for input
  setupI2S();
  
  setAudioState(AUDIO_IDLE);
  clearLEDs();
  
  Serial.println("🔊 Audio playback complete");
}

void sendAudioToServer() {
  if (!isConnected || audioBufferIndex == 0) {
    Serial.println("⚠️ Cannot send audio: not connected or no data");
    return;
  }
  
  Serial.println("📤 Sending audio to server...");
  
  setAudioState(AUDIO_SENDING);
  
  // Visual feedback
  setLEDColor("yellow", 100);
  
  // Send audio data via WebSocket
  sendAudioData(audioBuffer, audioBufferIndex);
  
  setAudioState(AUDIO_IDLE);
  clearLEDs();
  
  Serial.println("📤 Audio sent to server");
}

size_t readAudioData(uint8_t* buffer, size_t bufferSize) {
  size_t bytesRead = 0;
  
  esp_err_t result = i2s_read(I2S_NUM_0, buffer, bufferSize, &bytesRead, portMAX_DELAY);
  
  if (result != ESP_OK) {
    Serial.printf("❌ I2S read error: %s\n", esp_err_to_name(result));
    return 0;
  }
  
  return bytesRead;
}

void writeAudioData(uint8_t* buffer, size_t bufferSize) {
  size_t bytesWritten = 0;
  
  esp_err_t result = i2s_write(I2S_NUM_0, buffer, bufferSize, &bytesWritten, portMAX_DELAY);
  
  if (result != ESP_OK) {
    Serial.printf("❌ I2S write error: %s\n", esp_err_to_name(result));
  }
}

void setAudioState(AudioState state) {
  currentAudioState = state;
  
  const char* stateNames[] = {"IDLE", "RECORDING", "PLAYING", "SENDING"};
  Serial.printf("🎵 Audio state: %s\n", stateNames[state]);
}

AudioState getAudioState() {
  return currentAudioState;
}

void printAudioInfo() {
  Serial.println("=== 🎵 Audio Info ===");
  Serial.printf("Sample Rate: %d Hz\n", SAMPLE_RATE);
  Serial.printf("Bits per Sample: %d\n", SAMPLE_BITS);
  Serial.printf("Record Time: %d seconds\n", RECORD_TIME);
  Serial.printf("Buffer Size: %d bytes\n", BUFFER_SIZE);
  Serial.printf("Current State: %d\n", currentAudioState);
  Serial.printf("Buffer Index: %d\n", audioBufferIndex);
  Serial.println("====================");
}