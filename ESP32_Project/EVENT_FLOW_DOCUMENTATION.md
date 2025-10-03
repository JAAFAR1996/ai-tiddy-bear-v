# 🧸 AI Teddy Bear - Event Flow Documentation

## 📋 تسلسل الأحداث الكامل في النظام

### 🎯 **1. بدء التشغيل (System Startup)**

```
[INIT] System starting...
[SYS] Initializing hardware...
[WIFI] Connecting to network...
[SEC] Initializing security...
[AUTH] Starting authentication...
[WS] Initializing WebSocket...
[AUDIO] Initializing audio system...
[SYS] All systems ready!
```

### 🔐 **2. تدفق المصادقة (Authentication Flow)**

```
[AUTH] Starting device authentication...
[AUTH] Generating device ID...
[AUTH] Creating HMAC signature...
[HTTP] Sending claim request to server...
[HTTP] Server response: 200 OK
[AUTH] Parsing response JSON...
[AUTH] Saving tokens to NVS...
[AUTH] Authentication successful!
[WS] Connecting with JWT token...
[WS] WebSocket connected and authenticated
```

### 🎤 **3. تدفق الصوت الكامل (Complete Audio Flow)**

#### **3.1 بدء التسجيل (Recording Start)**
```
[BTN] Button pressed detected
[AUDIO] Starting real-time streaming...
[AUDIO] Initializing microphone...
[AUDIO] Starting audio capture task...
[AUDIO] Audio buffer allocated: 4096 bytes
[AUDIO] Recording started - State: RECORDING
```

#### **3.2 تسجيل الصوت (Audio Recording)**
```
[AUDIO] Capturing audio chunk: 4096 bytes
[AUDIO] Audio quality - RMS: -12.5 dBFS, Peak: 2048, Voice: YES
[AUDIO] Processing audio data...
[AUDIO] Applying noise reduction...
[AUDIO] Applying AGC (Auto Gain Control)...
[AUDIO] Voice activity detected!
```

#### **3.3 إرسال الصوت (Audio Transmission)**
```
[AUDIO] Preparing audio for transmission...
[AUDIO] Encoding audio to base64...
[AUDIO] Calculating HMAC for security...
[WS] Sending audio chunk to server...
[WS] Message: SEND audio_chunk (4096 bytes)
[WS] Audio chunk sent successfully in 45 ms
[AUDIO] Audio transmission complete
```

#### **3.4 معالجة السيرفر (Server Processing)**
```
[WS] Message: RECEIVE processing_status
[WS] Server processing audio...
[WS] Message: RECEIVE processing_progress (25%)
[WS] Message: RECEIVE processing_progress (50%)
[WS] Message: RECEIVE processing_progress (75%)
[WS] Message: RECEIVE processing_progress (100%)
[WS] Server processing complete
```

#### **3.5 استلام الرد (Response Reception)**
```
[WS] Message: RECEIVE audio_response
[AUDIO] Received audio response from server
[AUDIO] Response contains: text + audio data
[AUDIO] Audio format: PCM 16kHz mono s16le
[AUDIO] Audio size: 8192 bytes
[AUDIO] Decoding base64 audio data...
[AUDIO] Audio decoded successfully
```

#### **3.6 تشغيل الصوت (Audio Playback)**
```
[AUDIO] Starting audio playback...
[AUDIO] Setting volume to 70%
[AUDIO] Playing audio response...
[LED] Starting speaking animation (blue)
[AUDIO] Audio playback in progress...
[AUDIO] Playback complete - Duration: 2.5 seconds
[LED] Speaking animation complete
[AUDIO] Audio flow complete - State: IDLE
```

### 🔘 **4. تدفق تفاعل المستخدم (User Interaction Flow)**

#### **4.1 ضغط الزر (Button Press)**
```
[BTN] Button pressed detected
[BTN] Debouncing check passed
[BTN] Current context: WebSocket connected
[BTN] Action: Start audio recording
[AUDIO] Transitioning to RECORDING state
[LED] Recording indicator (red blinking)
```

#### **4.2 رفع الزر (Button Release)**
```
[BTN] Button released detected
[BTN] Current context: Audio recording active
[BTN] Action: Stop audio recording
[AUDIO] Transitioning to SENDING state
[AUDIO] Sending final audio chunk...
[AUDIO] Transitioning to PROCESSING state
[LED] Processing indicator (yellow)
```

### 🌐 **5. تدفق WebSocket (WebSocket Flow)**

#### **5.1 الاتصال (Connection)**
```
[WS] Attempting WebSocket connection...
[WS] Connecting to: wss://ai-tiddy-bear-v-xuqy.onrender.com/ws/esp32/connect
[WS] WebSocket connected successfully
[WS] Sending handshake message...
[WS] Handshake sent with device capabilities
[WS] Waiting for server acknowledgment...
[WS] Server acknowledged - Connection established
```

#### **5.2 المصادقة (Authentication)**
```
[WS] Sending JWT authentication...
[WS] JWT token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
[WS] Waiting for authentication response...
[WS] Authentication successful!
[WS] Device authenticated and ready
```

#### **5.3 إرسال الرسائل (Message Sending)**
```
[WS] Preparing message for transmission...
[WS] Message type: audio_chunk
[WS] Message size: 4096 bytes
[WS] Adding HMAC signature...
[WS] Sending message to server...
[WS] Message sent successfully
[WS] Waiting for acknowledgment...
[WS] Server acknowledged message
```

#### **5.4 استلام الرسائل (Message Reception)**
```
[WS] Message received from server
[WS] Message type: audio_response
[WS] Message size: 8192 bytes
[WS] Validating HMAC signature...
[WS] HMAC validation successful
[WS] Processing message...
[WS] Message processed successfully
```

### 🔄 **6. تدفق إعادة الاتصال (Reconnection Flow)**

```
[WS] WebSocket connection lost
[WS] Attempting automatic reconnection...
[WS] Reconnection attempt 1/3
[WS] Reconnection failed - retrying in 5 seconds
[WS] Reconnection attempt 2/3
[WS] Reconnection successful!
[WS] Re-authenticating device...
[AUTH] Re-authentication successful
[WS] WebSocket fully restored
```

### 📊 **7. إحصائيات النظام (System Statistics)**

```
[SYS] System Statistics:
[SYS] - Uptime: 3600 seconds (1 hour)
[SYS] - Free Heap: 245760 bytes
[SYS] - CPU Usage: 15.2%
[SYS] - WiFi Signal: -45 dBm
[SYS] - Audio Recorded: 1024000 bytes
[SYS] - Audio Sent: 1024000 bytes
[SYS] - Audio Received: 512000 bytes
[SYS] - Audio Played: 512000 bytes
[SYS] - WebSocket Messages Sent: 150
[SYS] - WebSocket Messages Received: 75
[SYS] - Button Presses: 25
[SYS] - Authentication Attempts: 1
[SYS] - Reconnection Attempts: 0
```

### 🎭 **8. تدفق الرسوم المتحركة (Animation Flow)**

```
[LED] Starting animation: speaking
[LED] Animation color: blue
[LED] Animation duration: 2500 ms
[LED] Animation pattern: breathing
[LED] Animation intensity: 70%
[LED] Animation complete
[LED] Returning to idle state
```

### 🔧 **9. تدفق معالجة الأخطاء (Error Handling Flow)**

```
[ERROR] Audio capture failed
[ERROR] Error details: I2S initialization failed
[ERROR] Attempting recovery...
[AUDIO] Reinitializing audio system...
[AUDIO] Audio system recovered successfully
[SUCCESS] Audio system fully operational
```

## 📈 **مثال على تسلسل كامل:**

```
[INIT] System starting...
[WIFI] Connected to network
[AUTH] Authentication successful
[WS] WebSocket connected
[BTN] Button pressed - Starting recording
[AUDIO] Recording started
[AUDIO] Captured chunk: 4096 bytes
[WS] Sending audio to server
[WS] Server processing...
[WS] Received audio response
[AUDIO] Playing response audio
[LED] Speaking animation
[AUDIO] Playback complete
[BTN] Button released - Recording stopped
[AUDIO] Audio flow complete
```

## 🎯 **الخلاصة:**

نعم! **الـ LOG سيعرض كل شيء** بتسلسل واضح ومفصل:

✅ **التقاط الصوت** - مع تفاصيل الجودة والحجم  
✅ **إرسال الصوت للسيرفر** - مع وقت الإرسال والنجاح/الفشل  
✅ **استلام الرد من السيرفر** - مع تفاصيل البيانات المستلمة  
✅ **معالجة الرد** - مع تفاصيل فك التشفير  
✅ **تشغيل الصوت** - مع تفاصيل التشغيل والرسوم المتحركة  
✅ **جميع الأحداث الأخرى** - المصادقة، WebSocket، الأزرار، إلخ  

**كل حدث له timestamp وcategory وتفاصيل واضحة!** 🚀
