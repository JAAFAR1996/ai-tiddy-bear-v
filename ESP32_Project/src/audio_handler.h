#ifndef AUDIO_HANDLER_H
#define AUDIO_HANDLER_H

#include <Arduino.h>
#include <driver/i2s.h>
#include <ArduinoJson.h>

// Audio configuration constants
#define SAMPLE_RATE 16000
#define RECORD_TIME 3  // seconds
#define AUDIO_CHUNK_SIZE 4096

// Audio states
typedef enum {
    AUDIO_IDLE,
    AUDIO_RECORDING,
    AUDIO_PLAYING,
    AUDIO_STREAMING,
    AUDIO_SENDING,
    AUDIO_ERROR
} AudioState;

// Audio processing structures
typedef struct {
    float noise_floor;
    float rms_level;
    bool is_active;
} NoiseProfile;

typedef struct {
    float target_level;
    float current_gain;
    bool enabled;
} AGCState;

typedef struct {
    bool voice_detected;
    float confidence;
    unsigned long last_activity;
} VADMetrics;

// Function declarations
bool initAudio();
void cleanupAudio();
void startRecording();
void stopRecording();
void playAudioResponse(uint8_t* audioData, size_t length);
void setAudioState(AudioState state);
AudioState getAudioState();
bool isRecording();
void sendAudioData(uint8_t* audioData, size_t length);
void handleAudioResponse(JsonObject params);
void startRealTimeStreaming();
void stopRealTimeStreaming();
void playTone(int frequency, int duration);

// Audio processing functions
String calculateAudioHMAC(uint8_t* audioData, size_t length, const String& chunkId, const String& sessionId);

// Global variables (extern)
extern AudioState currentAudioState;
extern NoiseProfile noiseProfile;
extern AGCState agcState;
extern VADMetrics vadMetrics;

#endif // AUDIO_HANDLER_H
