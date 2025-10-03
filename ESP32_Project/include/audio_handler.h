#ifndef AUDIO_HANDLER_H
#define AUDIO_HANDLER_H

#include "config.h"
#include <driver/i2s.h>

// Audio configuration
#define SAMPLE_RATE 16000
#define SAMPLE_BITS 16
#define RECORD_TIME 3  // seconds - optimized for memory usage
#define BUFFER_SIZE 8192  // Optimized: 8192 bytes per frame for better throughput
#define MIN_BUFFER_SIZE 2048  // Minimum buffer size for low-latency mode
#define MAX_BUFFER_SIZE 8192  // Maximum allowed buffer size

// Memory safety constants  
#define MIN_FREE_HEAP 32768   // Minimum free heap required for operations

// Audio enhancement constants
#define NOISE_GATE_THRESHOLD 800     // Noise gate threshold (0-32767)
#define VAD_ENERGY_THRESHOLD 1500    // Voice Activity Detection energy threshold
#define VAD_WINDOW_SIZE 160          // VAD analysis window (10ms at 16kHz)
#define AGC_TARGET_LEVEL 8000        // AGC target amplitude level
#define AGC_MAX_GAIN 8.0             // Maximum AGC gain multiplier
#define AGC_MIN_GAIN 0.125           // Minimum AGC gain multiplier
#define FILTER_ALPHA 0.95            // Low-pass filter coefficient for noise reduction
#define SPECTRAL_SUBTRACTION_ALPHA 2.0  // Spectral subtraction over-subtraction factor

// Audio states
enum AudioState {
  AUDIO_IDLE,
  AUDIO_RECORDING,
  AUDIO_STREAMING,    // ✅ إضافة للـ real-time streaming
  AUDIO_PLAYING,
  AUDIO_SENDING,
  AUDIO_ERROR
};

// Voice Activity Detection states
enum VADState {
  VAD_SILENCE,
  VAD_SPEECH,
  VAD_UNKNOWN
};

// Audio enhancement structures
struct NoiseProfile {
  float spectral_floor[256];    // Noise floor estimate for spectral subtraction
  float noise_estimate;         // Current noise level estimate
  bool profile_ready;           // Whether noise profile is calibrated
  uint32_t calibration_samples; // Number of samples used for calibration
};

struct AGCState {
  float current_gain;           // Current AGC gain
  float peak_level;             // Peak level tracker
  float rms_level;              // RMS level tracker
  float attack_time;            // AGC attack time constant
  float release_time;           // AGC release time constant
};

struct VADMetrics {
  float energy;                 // Current frame energy
  float zero_crossing_rate;     // Zero crossing rate
  VADState state;               // Current VAD state
  uint32_t speech_frames;       // Number of consecutive speech frames
  uint32_t silence_frames;      // Number of consecutive silence frames
};

extern AudioState currentAudioState;
extern volatile bool audioInitialized;

// Core audio functions
void initAudio();
void cleanupAudio();  // NEW: Proper cleanup function
void startRecording();
void stopRecording();
void startRealTimeStreaming();  // ✅ إضافة للـ push-to-talk
void stopRealTimeStreaming();   // ✅ إضافة للـ push-to-talk
bool isRecording();
void playAudioResponse(uint8_t* audioData, size_t length);
void sendAudioToServer();

// I2S functions with enhanced error handling
bool setupI2S();  // NEW: Returns bool for error checking
bool reconfigureI2SForOutput();  // NEW: Safe I2S reconfiguration
size_t readAudioData(uint8_t* buffer, size_t bufferSize);
void writeAudioData(uint8_t* buffer, size_t bufferSize);

// Production I2S with RTOS tasks and ring buffers
bool startI2STasks();
void stopI2STasks();
void audioCaptureTask(void* parameter);
void audioPlaybackTask(void* parameter);  
void websocketSendTask(void* parameter);

// Audio utilities
void setAudioState(AudioState state);
AudioState getAudioState();
void printAudioInfo();

// Adaptive buffer management
void setBufferSizeMode(int target_latency_ms);
int getCurrentBufferSize();
void optimizeBufferForLatency(bool low_latency_mode);

// Audio compression (simple RLE-based)
uint8_t* compressAudioData(uint8_t* data, size_t dataSize, size_t* compressedSize);
void decompressAudioData(uint8_t* compressedData, size_t compressedSize, uint8_t* outputData, size_t outputSize);

// Audio enhancement functions
void initAudioEnhancements();
void cleanupAudioEnhancements();

// Noise cancellation
void calibrateNoiseProfile(int16_t* samples, size_t sampleCount);
void applyNoiseReduction(int16_t* samples, size_t sampleCount);
void applyNoiseGate(int16_t* samples, size_t sampleCount);
void applySpectralSubtraction(int16_t* samples, size_t sampleCount);

// Voice Activity Detection (VAD)
VADState detectVoiceActivity(int16_t* samples, size_t sampleCount);
float calculateFrameEnergy(int16_t* samples, size_t sampleCount);
float calculateZeroCrossingRate(int16_t* samples, size_t sampleCount);
bool isVoicePresent();

// Automatic Gain Control (AGC)
void initAGC();
void applyAutomaticGainControl(int16_t* samples, size_t sampleCount);
float calculateRMSLevel(int16_t* samples, size_t sampleCount);
float calculatePeakLevel(int16_t* samples, size_t sampleCount);

// Audio quality optimization
void applyAudioEnhancements(int16_t* samples, size_t sampleCount);
void applyLowPassFilter(int16_t* samples, size_t sampleCount);
void applyHighPassFilter(int16_t* samples, size_t sampleCount);
void applyDynamicRangeCompression(int16_t* samples, size_t sampleCount);
void applyEchoSuppression(int16_t* samples, size_t sampleCount);

// Audio analysis and metrics
float getSignalToNoiseRatio();
float getCurrentAudioQuality();
void printAudioEnhancementStats();

// Global audio enhancement state
extern NoiseProfile noiseProfile;
extern AGCState agcState;
extern VADMetrics vadMetrics;

// Memory management functions (internal use)
// These are declared here for testing purposes but should be static in implementation
#ifdef AUDIO_TESTING
static bool allocateAudioBuffer();
static void deallocateAudioBuffer();
#endif

// Enhanced recording with audio processing
void startEnhancedRecording();
void processAudioFrame(int16_t* samples, size_t sampleCount);

// PAM8403 Audio System Functions
bool initAudioSystem();
void playTone(int frequency, int duration);
void setMasterVolume(int volume);
void cleanupAudioSystem();

// PAM8403 Pin Definitions - Use config.h definitions
// DAC pins are now properly defined in config.h to avoid I2S conflicts

#endif
