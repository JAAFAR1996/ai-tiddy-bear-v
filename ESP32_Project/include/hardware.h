#ifndef HARDWARE_H
#define HARDWARE_H

#include <FastLED.h>
#include <ESP32Servo.h>
#include "config.h"

extern CRGB leds[NUM_LEDS];
extern Servo headServo;

// Hardware initialization
void initHardware();

// LED Control
void setLEDColor(String color, int brightness = LED_BRIGHTNESS);
void setLEDColor(CRGB color, int brightness = LED_BRIGHTNESS);
void clearLEDs();

// Servo Control
void moveServo(String direction, int speed = 50);
void moveServo(int angle, int speed = 50);
void centerServo();

// Audio Control
void playTone(int frequency, int duration);
void playMelody(int* frequencies, int* durations, int length);

// Animations
void playWelcomeAnimation();
void playHappyAnimation();
void playSadAnimation();
void playExcitedAnimation();
void playRainbowAnimation();
void playBreathingAnimation(CRGB color);

// Utility functions
void blinkLED(CRGB color, int times = 3, int delayMs = 200);
void fadeInOut(CRGB color, int duration = 1000);

#endif