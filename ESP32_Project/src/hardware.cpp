#include "hardware.h"
#include "audio_handler.h"
#include "config.h"
#include <WiFi.h>
#include <Arduino.h>
#if AUDIO_USE_DAC
#include <driver/dac.h>
#endif

// 🧸 Audio-Only AI Teddy Bear Hardware
// Simple button + audio implementation - No visual components

// Reserve a dedicated LEDC channel for speaker tones (audio-only device)
static const int SPEAKER_LEDC_CHANNEL   = 0;   // 0..15 on ESP32
static const int SPEAKER_LEDC_RES_BITS  = 10;  // 10-bit resolution
static const int SPEAKER_LEDC_BASE_FREQ = 2000; // Base setup; actual tone sets runtime freq
// Limit duty to reduce amplifier surge current (0..(2^RES-1))
static const int SPEAKER_LEDC_DUTY_LIMIT = 24;  // ~2.3% at 10‑bit (max 1023)
static const int SPEAKER_LEDC_RAMP_STEP  = 2;   // step size for fade-in/out
static const int SPEAKER_LEDC_RAMP_DELAY_MS = 2; // per-step delay

// Hardware initialization
void initHardware() {
  // Initialize button pin with pullup (hidden inside teddy bear)
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  // Initialize speaker pin for audio output
  // Use LEDC PWM for reliable tone generation on ESP32
  // Pre-configure LEDC; attach on demand to avoid idle noise on amplifier input
  ledcSetup(SPEAKER_LEDC_CHANNEL, SPEAKER_LEDC_BASE_FREQ, SPEAKER_LEDC_RES_BITS);
  pinMode(SPEAKER_PIN, OUTPUT);
  digitalWrite(SPEAKER_PIN, LOW); // keep input referenced (no floating) when idle
  
  Serial.println("🧸 Teddy Bear hardware initialized (Audio-only mode)");
}

// 🧸 Audio-Only Functions (No LEDs in teddy bear design)
// All visual feedback removed - Teddy bear uses only audio interaction

// Simplified compatibility functions (no-op implementations)
void clearLEDs() { /* No LEDs in teddy bear */ }
void setLEDColor(String color, int brightness) { /* Audio-only teddy bear */ }
void setLEDColor(int r, int g, int b, int brightness) { /* Audio-only teddy bear */ }

// Note: playTone and playMelody are implemented in audio_handler.cpp

// Audio feedback for system status (replaces visual animations)
void playSystemSound(int frequency, int duration) {
#if AUDIO_USE_DAC
  // Simple DAC ramp on GPIO25 for smoother tone (8-bit)
  (void)frequency; // Basic DC ramp (no true sine without I2S)
  dacOutputEnable(DAC_CHANNEL_1); // GPIO25
  // Fade-in
  for (int v = 0; v <= 255; v += 4) { dacWrite(AUDIO_OUT_LEFT, v); delay(2); }
  int holdMs = duration - (2 * (255/4) * 2);
  if (holdMs < 0) holdMs = 0;
  if (holdMs > 0) delay(holdMs);
  // Fade-out
  for (int v = 255; v >= 0; v -= 4) { dacWrite(AUDIO_OUT_LEFT, v); delay(2); }
  dacWrite(AUDIO_OUT_LEFT, 0);
  dacOutputDisable(DAC_CHANNEL_1);
#else
  // Attach channel on demand to minimize idle hiss/buzz
  ledcAttachPin(SPEAKER_PIN, SPEAKER_LEDC_CHANNEL);
  // Generate tone using LEDC to avoid Tone task/initialization issues
  ledcWriteTone(SPEAKER_LEDC_CHANNEL, frequency);
  // Fade-in to reduce click/pop and sudden surge
  for (int d = 0; d <= SPEAKER_LEDC_DUTY_LIMIT; d += SPEAKER_LEDC_RAMP_STEP) {
    ledcWrite(SPEAKER_LEDC_CHANNEL, d);
    delay(SPEAKER_LEDC_RAMP_DELAY_MS);
  }
  // Hold tone for requested duration minus ramp time
  int holdMs = duration - (2 * ((SPEAKER_LEDC_DUTY_LIMIT / SPEAKER_LEDC_RAMP_STEP) * SPEAKER_LEDC_RAMP_DELAY_MS));
  if (holdMs < 0) holdMs = 0;
  if (holdMs > 0) delay(holdMs);
  // Fade-out
  for (int d = SPEAKER_LEDC_DUTY_LIMIT; d >= 0; d -= SPEAKER_LEDC_RAMP_STEP) {
    ledcWrite(SPEAKER_LEDC_CHANNEL, d);
    delay(SPEAKER_LEDC_RAMP_DELAY_MS);
  }
  // Detach and drive pin low to avoid idle buzz
  ledcDetachPin(SPEAKER_PIN);
  pinMode(SPEAKER_PIN, OUTPUT);
  digitalWrite(SPEAKER_PIN, LOW);
#endif
}

void playStartupSound() {
  // Teddy bear startup sound
  playSystemSound(1000, 200);
  delay(100);
  playSystemSound(1200, 200);
}

void playConnectionSound() {
  // WiFi connected sound
  playSystemSound(800, 100);
  delay(50);
  playSystemSound(1000, 100);
  delay(50);
  playSystemSound(1200, 150);
}

void playErrorSound() {
  // Error sound
  playSystemSound(400, 300);
  delay(100);
  playSystemSound(300, 300);
}

// Compatibility stubs (no-op since no LEDs exist)
void playStreamingAnimation() { /* Audio-only mode */ }
void playHappyAnimation() { /* Audio-only mode */ }
void playSadAnimation() { /* Audio-only mode */ }
void playExcitedAnimation() { /* Audio-only mode */ }
void playWelcomeAnimation() { playStartupSound(); }
void playRainbowAnimation() { /* Audio-only mode */ }
void playBreathingAnimation(int r, int g, int b) { /* Audio-only mode */ }
void blinkLED(int r, int g, int b, int times, int delayMs) { /* Audio-only mode */ }
void fadeInOut(int r, int g, int b, int duration) { /* Audio-only mode */ }

void setLEDAnimation(int mode, int r, int g, int b, uint8_t brightness) { /* Audio-only mode */ }
void setBreathingMode(int r, int g, int b, uint8_t brightness) { /* Audio-only mode */ }
void setPulseMode(int r, int g, int b, uint8_t brightness) { /* Audio-only mode */ }

void showAudioReactive(bool enabled) { /* Audio-only mode */ }
void showNetworkStatus(bool show) { if(show) playConnectionSound(); }
void showBatteryLevel(bool show) { /* Audio-only mode */ }
void setRainbowMode(uint8_t brightness) { /* Audio-only mode */ }
void setAudioReactiveMode(bool enabled) { /* Audio-only mode */ }

// System compatibility stubs
void updateLEDAnimationSystem() { /* No LEDs */ }
void updateAudioReactiveAnimation() { /* No LEDs */ }
void updateNetworkStatusAnimation() { /* No LEDs */ }
void updateBatteryLevelAnimation() { /* No LEDs */ }
void updateBreathingAnimation() { /* No LEDs */ }
void updateRainbowAnimation() { /* No LEDs */ }
void updatePulseAnimation() { /* No LEDs */ }
void updateLEDTransition() { /* No LEDs */ }
void updateAudioLevel(uint16_t level) { /* Audio processing in audio_handler.cpp */ }
void updateBatteryStatus(float percent, bool charging) { /* No visual indicators */ }
void updateNetworkStatus(int rssi, bool connected, float quality) { /* No visual indicators */ }

int getCurrentLEDMode() { return 0; }
bool isLEDTransitioning() { return false; }
void setLEDAnimationSpeed(uint16_t speedMs) { /* No LEDs */ }
