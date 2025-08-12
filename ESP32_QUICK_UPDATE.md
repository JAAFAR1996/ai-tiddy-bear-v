# 🚨 ESP32 Quick Update Instructions

## ✅ Code Updated!

The ESP32 Arduino code has been updated to work with the new server. 

### 📋 What You Need To Do:

1. **Open Arduino IDE**
2. **Open file**: `ESP32_TeddyBear_Client.ino` 
3. **Update WiFi credentials**:
   ```cpp
   const char* ssid = "YOUR_WIFI_SSID";        // Replace with your WiFi name
   const char* password = "YOUR_WIFI_PASSWORD"; // Replace with your WiFi password
   ```

4. **Select Board**: Tools → Board → ESP32 Dev Module
5. **Select Port**: Tools → Port → (your ESP32 port)
6. **Upload**: Click Upload button ⬆️

### 📡 Server Settings (Already Updated):
- **Host**: ai-tiddy-bear-v-xuqy.onrender.com ✅
- **Port**: 443 (HTTPS) ✅
- **WebSocket**: /api/v1/esp32/chat ✅

### 🧪 Expected Serial Monitor Output:
```
🧸 AI Teddy Bear ESP32 Client Starting...
📡 Connecting to WiFi: YOUR_WIFI_SSID
✅ WiFi Connected!
📍 IP Address: 192.168.1.100
✅ WebSocket Connected to Teddy Bear Server!
📤 Sent connection message to server
```

### 🔧 WiFi Tips:
- Move ESP32 closer to router for better signal
- Use 2.4GHz WiFi (not 5GHz)
- Ensure WiFi password is correct

### 🎯 Test:
1. Press BOOT button on ESP32
2. Should send test message: "Hello, I'm your teddy bear!"
3. Watch for server response in Serial Monitor

**Ready to connect! 🚀**