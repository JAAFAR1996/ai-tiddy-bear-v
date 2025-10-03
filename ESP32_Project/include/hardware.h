#ifndef HARDWARE_H
#define HARDWARE_H

#include "config.h"

// 🧸 AUDIO-ONLY TEDDY BEAR - NO LEDS
// Hardware initialization
void initHardware();

// Audio Control - Teddy Bear Audio System
void playTone(int frequency, int duration);
void playMelody(int* frequencies, int* durations, int length);

// Audio animations (sound-only)
void playWelcomeAnimation();
void playHappyAnimation();  
void playSadAnimation();
void playExcitedAnimation();
void playStreamingAnimation();
void playRainbowAnimation();

// LED stub functions (audio-only teddy - no actual LEDs)
void setLEDColor(String color, int brightness = 50);
void setLEDColor(int r, int g, int b, int brightness = 50);
void clearLEDs();

#endif