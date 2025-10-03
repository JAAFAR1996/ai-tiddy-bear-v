#ifndef SETUP_HELPER_H
#define SETUP_HELPER_H

#include <Arduino.h>

// Interactive setup functions
void setupWiFiInteractive();
void setupDeviceInteractive();
void setupChildInteractive();
void runInteractiveSetup();

// Utility functions
String waitForSerialInput();
void checkSetupButton();
void showAvailableNetworks();

#endif