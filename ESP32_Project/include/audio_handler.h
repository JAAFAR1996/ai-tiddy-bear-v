#ifndef AUDIO_HANDLER_H
#define AUDIO_HANDLER_H

#include "config.h"
#include <driver/i2s.h>

// Audio configuration
#define SAMPLE_RATE 16000
#define SAMPLE_BITS 16
#define RECORD_TIME 3  // seconds - reduced from 5 to save memory
#define BUFFER_SIZE 512  // reduced from 1024 to save memory

// Audio states
enum AudioState {
  AUDIO_IDLE,
  AUDIO_RECORDING,
  AUDIO_PLAYING,
  AUDIO_SENDING
};

extern AudioState currentAudioState;

// Audio functions
void initAudio();
void startRecording();
void stopRecording();
bool isRecording();
void playAudioResponse(uint8_t* audioData, size_t length);
void sendAudioToServer();

// I2S functions
void setupI2S();
size_t readAudioData(uint8_t* buffer, size_t bufferSize);
void writeAudioData(uint8_t* buffer, size_t bufferSize);

// Audio utilities
void setAudioState(AudioState state);
AudioState getAudioState();
void printAudioInfo();

#endif