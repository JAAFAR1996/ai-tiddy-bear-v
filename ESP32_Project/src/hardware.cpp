#include "hardware.h"
#include <WiFi.h>

CRGB leds[NUM_LEDS];
Servo headServo;

void initHardware() {
  Serial.println("🔧 Initializing hardware...");
  
  // Initialize LEDs
  FastLED.addLeds<WS2812, LED_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(LED_BRIGHTNESS);
  FastLED.clear();
  FastLED.show();
  
  // Initialize Servo
  headServo.attach(SERVO_PIN);
  headServo.write(SERVO_CENTER);
  
  // Initialize Pins
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(SPEAKER_PIN, OUTPUT);
  
  // Welcome animation
  playWelcomeAnimation();
  
  Serial.println("✅ Hardware initialized!");
}

void setLEDColor(String color, int brightness) {
  CRGB ledColor = CRGB::White;
  
  if (color == "red") ledColor = CRGB::Red;
  else if (color == "green") ledColor = CRGB::Green;
  else if (color == "blue") ledColor = CRGB::Blue;
  else if (color == "yellow") ledColor = CRGB::Yellow;
  else if (color == "purple") ledColor = CRGB::Purple;
  else if (color == "orange") ledColor = CRGB::Orange;
  else if (color == "pink") ledColor = CRGB::Pink;
  else if (color == "off") ledColor = CRGB::Black;
  
  FastLED.setBrightness(constrain(brightness, 0, 255));
  fill_solid(leds, NUM_LEDS, ledColor);
  FastLED.show();
  
  Serial.printf("💡 LED: %s, Brightness: %d\n", color.c_str(), brightness);
}

void setLEDColor(CRGB color, int brightness) {
  FastLED.setBrightness(constrain(brightness, 0, 255));
  fill_solid(leds, NUM_LEDS, color);
  FastLED.show();
}

void clearLEDs() {
  FastLED.clear();
  FastLED.show();
}

void moveServo(String direction, int speed) {
  int angle = SERVO_CENTER;
  
  if (direction == "left") angle = SERVO_LEFT;
  else if (direction == "right") angle = SERVO_RIGHT;
  else if (direction == "up") angle = SERVO_UP;
  else if (direction == "down") angle = SERVO_DOWN;
  else if (direction == "center") angle = SERVO_CENTER;
  
  moveServo(angle, speed);
  
  Serial.printf("🤖 Servo: %s (angle: %d), Speed: %d\n", 
                direction.c_str(), angle, speed);
}

void moveServo(int angle, int speed) {
  int currentAngle = headServo.read();
  int step = (angle > currentAngle) ? 1 : -1;
  int delayTime = map(speed, 0, 100, 50, 5);
  
  while (currentAngle != angle) {
    currentAngle += step;
    headServo.write(currentAngle);
    delay(delayTime);
  }
}

void centerServo() {
  headServo.write(SERVO_CENTER);
}

void playTone(int frequency, int duration) {
  ledcSetup(0, frequency, 8);
  ledcAttachPin(SPEAKER_PIN, 0);
  ledcWrite(0, 128); // 50% duty cycle
  delay(duration);
  ledcWrite(0, 0);
  
  Serial.printf("🔊 Tone: %d Hz, Duration: %d ms\n", frequency, duration);
}

void playMelody(int* frequencies, int* durations, int length) {
  for (int i = 0; i < length; i++) {
    playTone(frequencies[i], durations[i]);
    delay(50); // Small pause between notes
  }
}

// Animations
void playWelcomeAnimation() {
  Serial.println("🎭 Welcome animation");
  
  // Rainbow wave
  for(int hue = 0; hue < 255; hue += 10) {
    for(int i = 0; i < NUM_LEDS; i++) {
      leds[i] = CHSV(hue + (i * 15), 255, 150);
    }
    FastLED.show();
    delay(50);
  }
  
  clearLEDs();
}

void playHappyAnimation() {
  Serial.println("😊 Happy animation");
  
  // Yellow pulse
  for(int brightness = 0; brightness <= 255; brightness += 15) {
    setLEDColor(CRGB(brightness, brightness, 0), brightness);
    delay(30);
  }
  
  delay(300);
  
  for(int brightness = 255; brightness >= 0; brightness -= 15) {
    setLEDColor(CRGB(brightness, brightness, 0), brightness);
    delay(30);
  }
  
  clearLEDs();
}

void playSadAnimation() {
  Serial.println("😢 Sad animation");
  
  // Slow blue fade
  for(int brightness = 0; brightness <= 100; brightness += 5) {
    setLEDColor(CRGB(0, 0, brightness), brightness);
    delay(50);
  }
  
  delay(1000);
  clearLEDs();
}

void playExcitedAnimation() {
  Serial.println("🎉 Excited animation");
  
  // Fast rainbow strobe
  for(int cycle = 0; cycle < 8; cycle++) {
    for(int i = 0; i < NUM_LEDS; i++) {
      leds[i] = CHSV(random(0, 255), 255, 255);
    }
    FastLED.show();
    delay(100);
    clearLEDs();
    delay(50);
  }
}

void playRainbowAnimation() {
  Serial.println("🌈 Rainbow animation");
  
  for(int hue = 0; hue < 255; hue += 5) {
    fill_solid(leds, NUM_LEDS, CHSV(hue, 255, 200));
    FastLED.show();
    delay(20);
  }
  
  clearLEDs();
}

void playBreathingAnimation(CRGB color) {
  // Breathing effect
  for(int brightness = 0; brightness <= 255; brightness += 5) {
    setLEDColor(color, brightness);
    delay(20);
  }
  
  for(int brightness = 255; brightness >= 0; brightness -= 5) {
    setLEDColor(color, brightness);
    delay(20);
  }
}

void blinkLED(CRGB color, int times, int delayMs) {
  for(int i = 0; i < times; i++) {
    setLEDColor(color, LED_BRIGHTNESS);
    delay(delayMs);
    clearLEDs();
    delay(delayMs);
  }
}

void fadeInOut(CRGB color, int duration) {
  int steps = 50;
  int stepDelay = duration / (steps * 2);
  
  // Fade in
  for(int i = 0; i <= steps; i++) {
    int brightness = map(i, 0, steps, 0, 255);
    setLEDColor(color, brightness);
    delay(stepDelay);
  }
  
  // Fade out
  for(int i = steps; i >= 0; i--) {
    int brightness = map(i, 0, steps, 0, 255);
    setLEDColor(color, brightness);
    delay(stepDelay);
  }
}