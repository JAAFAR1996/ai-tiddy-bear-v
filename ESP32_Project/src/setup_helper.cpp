#include "setup_helper.h"
#include "config_manager.h"
#include "hardware.h"
#include <WiFi.h>

void setupWiFiInteractive() {
    Serial.println("\n🔧 WiFi Setup Helper");
    Serial.println("====================");
    
    ConfigManager& configMgr = getConfigManager();
    
    // Scan for available networks
    Serial.println("📡 Scanning for WiFi networks...");
    WiFi.mode(WIFI_STA);
    int n = WiFi.scanNetworks();
    
    if (n == 0) {
        Serial.println("❌ No networks found");
        return;
    }
    
    Serial.printf("✅ Found %d networks:\n", n);
    for (int i = 0; i < n; ++i) {
        Serial.printf("%d: %s (%d dBm) %s\n", 
                     i + 1, 
                     WiFi.SSID(i).c_str(), 
                     WiFi.RSSI(i),
                     (WiFi.encryptionType(i) == WIFI_AUTH_OPEN) ? "Open" : "Encrypted");
    }
    
    // Get user input
    Serial.println("\nEnter WiFi SSID (or network number):");
    String ssid = waitForSerialInput();
    
    // Check if user entered a number
    int networkIndex = ssid.toInt();
    if (networkIndex > 0 && networkIndex <= n) {
        ssid = WiFi.SSID(networkIndex - 1);
        Serial.printf("Selected: %s\n", ssid.c_str());
    }
    
    Serial.println("Enter WiFi Password (leave empty for open networks):");
    String password = waitForSerialInput();
    
    // Test connection
    Serial.printf("🔗 Testing connection to %s...\n", ssid.c_str());
    WiFi.begin(ssid.c_str(), password.c_str());
    
    unsigned long startTime = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startTime < 15000) {
        delay(500);
        Serial.print(".");
        setLEDColor("blue", 50);
        delay(100);
        clearLEDs();
        delay(100);
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n✅ WiFi connection successful!");
        Serial.printf("IP Address: %s\n", WiFi.localIP().toString().c_str());
        
        // Save configuration
        configMgr.setWiFiCredentials(ssid, password);
        
        setLEDColor("green", 100);
        delay(1000);
        clearLEDs();
    } else {
        Serial.println("\n❌ WiFi connection failed!");
        setLEDColor("red", 100);
        delay(1000);
        clearLEDs();
    }
}

void setupDeviceInteractive() {
    Serial.println("\n🔧 Device Setup Helper");
    Serial.println("======================");
    
    ConfigManager& configMgr = getConfigManager();
    TeddyConfig& config = configMgr.getConfig();
    
    Serial.printf("Current Device ID: %s\n", config.device_id.c_str());
    Serial.println("Enter new Device ID (or press Enter to keep current):");
    String deviceId = waitForSerialInput();
    if (deviceId.length() == 0) {
        deviceId = config.device_id;
    }
    
    Serial.printf("Current Server Host: %s\n", config.server_host.c_str());
    Serial.println("Enter Server Host (or press Enter to keep current):");
    String serverHost = waitForSerialInput();
    if (serverHost.length() == 0) {
        serverHost = config.server_host;
    }
    
    Serial.println("Enter Device Secret Key:");
    String deviceSecret = waitForSerialInput();
    
    // Update configuration
    configMgr.setDeviceInfo(deviceId, deviceSecret);
    config.server_host = serverHost;
    configMgr.saveConfiguration();
    
    Serial.println("✅ Device configuration updated!");
}

void setupChildInteractive() {
    Serial.println("\n🔧 Child Profile Setup");
    Serial.println("======================");
    
    ConfigManager& configMgr = getConfigManager();
    
    Serial.println("Enter Child ID:");
    String childId = waitForSerialInput();
    
    Serial.println("Enter Child Name:");
    String childName = waitForSerialInput();
    
    Serial.println("Enter Child Age:");
    String ageStr = waitForSerialInput();
    int childAge = ageStr.toInt();
    if (childAge <= 0) {
        childAge = 7; // Default age
    }
    
    // Update configuration
    configMgr.setChildInfo(childId, childName, childAge);
    
    Serial.println("✅ Child profile configured!");
}

void showAvailableNetworks() {
    Serial.println("\n📡 Scanning for WiFi networks...");
    setLEDColor("blue", 50);
    
    WiFi.mode(WIFI_STA);
    int n = WiFi.scanNetworks();
    
    clearLEDs();
    
    if (n == 0) {
        Serial.println("❌ No networks found");
        setLEDColor("red", 100);
        delay(1000);
        clearLEDs();
        return;
    }
    
    Serial.println("\n📋 Available WiFi Networks:");
    Serial.println("============================");
    
    for (int i = 0; i < n; ++i) {
        String encryption = "";
        switch (WiFi.encryptionType(i)) {
            case WIFI_AUTH_OPEN:
                encryption = "Open";
                break;
            case WIFI_AUTH_WEP:
                encryption = "WEP";
                break;
            case WIFI_AUTH_WPA_PSK:
                encryption = "WPA";
                break;
            case WIFI_AUTH_WPA2_PSK:
                encryption = "WPA2";
                break;
            case WIFI_AUTH_WPA_WPA2_PSK:
                encryption = "WPA/WPA2";
                break;
            case WIFI_AUTH_WPA2_ENTERPRISE:
                encryption = "WPA2-Enterprise";
                break;
            default:
                encryption = "Unknown";
                break;
        }
        
        Serial.printf("%2d: %-32s | %3d dBm | %s\n", 
                     i + 1, 
                     WiFi.SSID(i).c_str(), 
                     WiFi.RSSI(i),
                     encryption.c_str());
    }
    
    Serial.println("============================");
    Serial.printf("Found %d networks\n\n", n);
    
    // Success indication
    setLEDColor("green", 100);
    delay(500);
    clearLEDs();
}

void runInteractiveSetup() {
    Serial.println("\n🧸 AI Teddy Bear Interactive Setup");
    Serial.println("===================================");
    
    ConfigManager& configMgr = getConfigManager();
    
    while (true) {
        Serial.println("\nSetup Menu:");
        Serial.println("1. WiFi Configuration");
        Serial.println("2. Device Configuration");
        Serial.println("3. Child Profile");
        Serial.println("4. View Current Configuration");
        Serial.println("5. Scan WiFi Networks");
        Serial.println("6. Reset All Configuration");
        Serial.println("7. Exit Setup");
        Serial.println("\nEnter your choice (1-7):");
        
        String choice = waitForSerialInput();
        
        if (choice == "1") {
            setupWiFiInteractive();
        } else if (choice == "2") {
            setupDeviceInteractive();
        } else if (choice == "3") {
            setupChildInteractive();
        } else if (choice == "4") {
            configMgr.getConfig(); // This will print the configuration
        } else if (choice == "5") {
            showAvailableNetworks();
        } else if (choice == "6") {
            Serial.println("⚠️ Are you sure you want to reset all configuration? (y/N):");
            String confirm = waitForSerialInput();
            if (confirm.equalsIgnoreCase("y") || confirm.equalsIgnoreCase("yes")) {
                configMgr.resetConfiguration();
                Serial.println("✅ Configuration reset complete!");
            }
        } else if (choice == "7") {
            Serial.println("✅ Setup complete!");
            break;
        } else {
            Serial.println("❌ Invalid choice. Please try again.");
        }
    }
}

String waitForSerialInput() {
    String input = "";
    unsigned long timeout = millis() + 30000; // 30 second timeout
    
    while (millis() < timeout) {
        if (Serial.available()) {
            char c = Serial.read();
            if (c == '\n' || c == '\r') {
                if (input.length() > 0) {
                    break;
                }
            } else if (c >= 32 && c <= 126) { // Printable characters
                input += c;
                Serial.print(c); // Echo character
            }
        }
        delay(10);
    }
    
    Serial.println(); // New line after input
    return input;
}

void checkSetupButton() {
    static unsigned long lastButtonCheck = 0;
    static int buttonPressCount = 0;
    static unsigned long firstPress = 0;
    
    if (millis() - lastButtonCheck > 100) { // Check every 100ms
        lastButtonCheck = millis();
        
        if (digitalRead(BUTTON_PIN) == LOW) {
            if (buttonPressCount == 0) {
                firstPress = millis();
            }
            buttonPressCount++;
            
            // If button pressed 5 times within 3 seconds, start setup
            if (buttonPressCount >= 5 && (millis() - firstPress) < 3000) {
                Serial.println("\n🔧 Setup mode activated by button sequence!");
                
                // Visual indication
                for (int i = 0; i < 5; i++) {
                    setLEDColor("purple", 100);
                    delay(200);
                    clearLEDs();
                    delay(200);
                }
                
                runInteractiveSetup();
                buttonPressCount = 0;
            }
        }
        
        // Reset counter after 3 seconds
        if (millis() - firstPress > 3000) {
            buttonPressCount = 0;
        }
    }
}