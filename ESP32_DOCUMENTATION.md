# 📋 ESP32 Teddy Bear - وثائق النظام التقنية

## 1. نظرة عامة على جهاز ESP32

جهاز ESP32 هو قلب الدمية الذكية، يعمل كجسر بين الطفل والخادم الخلفي، مع توفير تفاعل صوتي آني وآمن.

### المواصفات الأساسية
- **المعالج**: ESP32-S3-WROOM-32U (Dual-core Xtensa LX7 @ 240MHz)
- **الذاكرة**: 512 KB SRAM, 384 KB ROM, 16MB Flash, 8MB PSRAM
- **الاتصال**: WiFi 802.11 b/g/n, BLE 5.0 + Mesh
- **الصوت**: ميكروفون MEMS (I2S) + مكبر صوت 3W (I2S)
- **التغذية**: بطارية Li-Po 3.7V 2000mAh + USB-C
- **البرمجة**: ESP-IDF 5.0+ / Arduino Core
- **Security**: RSA-3072 based Secure Boot, AES-256 Flash Encryption

## 2. البنية المعمارية

```mermaid
graph TB
    subgraph "ESP32 Hardware"
        MIC[Microphone MEMS]
        SPK[Speaker 3W]
        BTN[Reset Button]
        LED[Status LED RGB]
        WIFI[WiFi Module]
        BLE[BLE Module]
    end
    
    subgraph "Software Components"
        AUDIO[Audio Processing]
        WS[WebSocket Client]
        NVS[NVS Storage]
        SEC[Security Module]
        PROV[BLE Provisioning]
    end
    
    subgraph "External Connections"
        APP[Parent App]
        SERVER[Backend Server]
    end
    
    MIC --> AUDIO
    AUDIO --> WS
    WS --> SERVER
    SERVER --> WS
    WS --> AUDIO
    AUDIO --> SPK
    
    APP -.->|BLE| PROV
    PROV --> NVS
    NVS --> WS
    
    LED --> SEC
    BTN --> PROV
```

## 3. تدفق العمليات الأساسية

### 3.1 عملية الإقران (Pairing Process)

```mermaid
sequenceDiagram
    autonumber
    participant LED as Status LED
    participant BLE as BLE Module
    participant APP as Parent App
    participant NVS as NVS Storage
    participant WiFi as WiFi Module
    participant Server as Backend Server
    
    Note over LED: Blue Blinking (Pairing Mode)
    BLE->>BLE: Advertise Service UUID
    APP->>BLE: Connect to Service
    APP->>BLE: Write Encrypted Payload
    Note over BLE: Decrypt with PoP Key
    BLE->>NVS: Store Credentials
    NVS-->>BLE: ACK
    BLE-->>APP: {"status": "ok"}
    
    WiFi->>WiFi: Connect to SSID
    Note over LED: Yellow (Connecting)
    WiFi->>Server: POST /device/session
    Server-->>WiFi: JWT Token
    WiFi->>NVS: Store JWT
    Note over LED: Green (Connected)
```

### 3.2 تدفق الصوت (Audio Stream Flow)

```mermaid
flowchart LR
    subgraph "Audio Capture"
        M[Mic Input] --> ADC[ADC 16kHz]
        ADC --> BUF1[Ring Buffer 4KB]
    end
    
    subgraph "Processing"
        BUF1 --> PCM[PCM Encoder]
        PCM --> CHUNK[4096B Chunks]
    end
    
    subgraph "Transmission"
        CHUNK --> WS1[WS Binary Frame]
        WS1 --> SERVER[Server STT/AI/TTS]
        SERVER --> WS2[WS Binary Response]
    end
    
    subgraph "Playback"
        WS2 --> BUF2[Output Buffer]
        BUF2 --> DAC[DAC 16kHz]
        DAC --> SPK[Speaker Output]
    end
```

## 4. بروتوكول WebSocket

### 4.1 الاتصال الأولي

```c
// WebSocket URL Construction
char ws_url[256];
sprintf(ws_url, "%s://%s:%d/esp32/connect?device_id=%s&child_id=%s&auth=%s",
    ssl_enabled ? "wss" : "ws",
    server_host,
    server_port,
    device_id,
    child_id,
    jwt_token);
```

### 4.2 أنواع الرسائل

#### رسائل التحكم (JSON Text Frames)

```json
// Welcome Message (Server → ESP32)
{
    "type": "welcome",
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "format": "pcm_s16le"
    }
}

// Policy Update (Server → ESP32)
{
    "type": "policy",
    "child_id": "uuid",
    "age": 7,
    "filters": {
        "content": "strict",
        "blocked_topics": ["violence", "personal_data"]
    }
}

// Token Refresh Request (ESP32 → Server)
{
    "type": "auth/refresh",
    "proof": "nonce-string"
}

// Token Refresh Response (Server → ESP32)
{
    "type": "auth/ok",
    "exp_in_sec": 300
}

// Alert Message (Server → ESP32)
{
    "type": "alert",
    "severity": "high",
    "code": "pii_detected",
    "message": "Sensitive info detected"
}
```

#### رسائل الصوت (Binary Frames)
- **الحجم**: 4096 بايت لكل إطار
- **التنسيق**: PCM 16kHz, Mono, 16-bit signed
- **الاتجاه**: ثنائي (ESP32 ↔ Server)

## 5. إدارة التخزين (NVS)

### 5.1 مفاتيح التخزين

```c
// NVS Namespace: "teddy_config"

typedef struct {
    char ssid[64];           // WiFi SSID
    char password[64];       // WiFi Password  
    char child_id[37];       // UUID format
    char device_id[37];      // Generated UUID
    char pairing_code[11];   // Format: XX-XX-XX
    char server_host[128];   // Backend host
    uint16_t server_port;    // Backend port
    bool ssl_enabled;        // Use WSS/WS
    char jwt_token[512];     // Current JWT
    uint32_t jwt_exp;        // JWT expiry timestamp
} device_config_t;
```

### 5.2 تدفق التخزين

```mermaid
stateDiagram-v2
    [*] --> FirstBoot: No Config
    FirstBoot --> BLEPairing: Button Press
    BLEPairing --> StoreConfig: Receive Credentials
    StoreConfig --> ConnectWiFi: Config Saved
    ConnectWiFi --> GetJWT: WiFi Connected
    GetJWT --> StoreJWT: Receive Token
    StoreJWT --> ActiveSession: JWT Stored
    ActiveSession --> RefreshJWT: Before Expiry
    RefreshJWT --> StoreJWT: New Token
    ActiveSession --> [*]: Shutdown
```

## 6. معالجة الصوت

### 6.1 مواصفات الصوت

| المعامل | القيمة |
|---------|--------|
| Sample Rate | 16000 Hz |
| Bit Depth | 16 bits |
| Channels | 1 (Mono) |
| Frame Size | 4096 bytes |
| Buffer Size | 8192 bytes |
| Latency | < 100ms |

### 6.2 خوارزمية المعالجة

```c
// Audio Processing Pipeline
void audio_task(void *pvParameters) {
    int16_t audio_buffer[2048];  // 4096 bytes
    
    while (1) {
        // 1. Capture from Microphone
        size_t bytes_read = i2s_read(I2S_NUM_0, 
                                     audio_buffer, 
                                     sizeof(audio_buffer),
                                     &bytes_read, 
                                     portMAX_DELAY);
        
        // 2. Apply Noise Reduction
        apply_noise_gate(audio_buffer, 2048, NOISE_THRESHOLD);
        
        // 3. Check Voice Activity
        if (detect_voice_activity(audio_buffer, 2048)) {
            // 4. Send to Server
            ws_send_binary(audio_buffer, bytes_read);
        }
        
        // 5. Check for Server Response
        if (ws_has_audio_response()) {
            ws_receive_audio(audio_buffer, sizeof(audio_buffer));
            
            // 6. Play through Speaker
            i2s_write(I2S_NUM_1, 
                     audio_buffer, 
                     bytes_read,
                     &bytes_written, 
                     portMAX_DELAY);
        }
    }
}
```

## 7. الأمان والحماية

### 7.1 آليات الأمان

```mermaid
graph TB
    subgraph "Security Layers"
        A[BLE Encryption with PoP Key]
        B[JWT Authentication 5min TTL]
        C[TLS/SSL for WebSocket]
        D[NVS Encryption]
        E[Secure Boot]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
```

### 7.2 تدفق المصادقة

```c
// JWT Validation and Refresh
typedef struct {
    char token[512];
    uint32_t issued_at;
    uint32_t expires_at;
} jwt_session_t;

bool validate_and_refresh_jwt(jwt_session_t *session) {
    uint32_t current_time = get_unix_timestamp();
    
    // Check if token needs refresh (60s before expiry)
    if (current_time > (session->expires_at - 60)) {
        // Send refresh request
        cJSON *refresh_req = cJSON_CreateObject();
        cJSON_AddStringToObject(refresh_req, "type", "auth/refresh");
        cJSON_AddStringToObject(refresh_req, "proof", generate_nonce());
        
        ws_send_json(refresh_req);
        
        // Wait for response
        cJSON *response = ws_receive_json(1000);
        if (cJSON_GetObjectItem(response, "type")->valuestring == "auth/ok") {
            // Update session
            session->expires_at = current_time + 
                cJSON_GetObjectItem(response, "exp_in_sec")->valueint;
            return true;
        }
        return false;
    }
    return true;
}
```

## 8. حالات LED والتشخيص

### 8.1 أنماط LED

| اللون | النمط | الحالة |
|-------|-------|--------|
| 🔵 أزرق | وميض بطيء | وضع الإقران |
| 🟡 أصفر | ثابت | جاري الاتصال |
| 🟢 أخضر | ثابت | متصل وجاهز |
| 🟢 أخضر | وميض سريع | جاري التحدث |
| 🔴 أحمر | وميض | خطأ في الاتصال |
| 🟣 بنفسجي | نبضة | تحديث البرامج |

### 8.2 رموز الأخطاء

```c
typedef enum {
    ERR_NONE = 0,
    ERR_WIFI_FAIL = 1,      // Red blink 1x
    ERR_SERVER_FAIL = 2,     // Red blink 2x
    ERR_AUTH_FAIL = 3,       // Red blink 3x
    ERR_AUDIO_FAIL = 4,      // Red blink 4x
    ERR_MEMORY_FULL = 5,     // Red blink 5x
} error_code_t;

void indicate_error(error_code_t code) {
    for (int i = 0; i < code; i++) {
        set_led_color(255, 0, 0);  // Red
        vTaskDelay(250 / portTICK_PERIOD_MS);
        set_led_color(0, 0, 0);    // Off
        vTaskDelay(250 / portTICK_PERIOD_MS);
    }
}
```

## 9. إدارة الطاقة

### 9.1 أوضاع الطاقة

```mermaid
stateDiagram-v2
    [*] --> Active: Voice Detected
    Active --> Idle: No Activity 30s
    Idle --> DeepSleep: No Activity 5min
    DeepSleep --> Active: Button Press
    Active --> Charging: USB Connected
    Charging --> Active: USB Disconnected
```

### 9.2 استهلاك الطاقة

| الوضع | الاستهلاك | مدة البطارية |
|-------|-----------|--------------|
| Active (Streaming) | 150mA | ~13 ساعة |
| Idle (WiFi On) | 80mA | ~25 ساعة |
| Deep Sleep | 10µA | ~6 أشهر |
| Charging | +500mA | 4 ساعات |

## 10. تحديثات OTA

### 10.1 تدفق التحديث

```c
// OTA Update Process
void perform_ota_update(const char *update_url) {
    esp_http_client_config_t config = {
        .url = update_url,
        .cert_pem = server_cert_pem,
        .timeout_ms = 5000,
    };
    
    // Indicate OTA start
    set_led_color(128, 0, 255);  // Purple pulse
    
    esp_err_t ret = esp_https_ota(&config);
    
    if (ret == ESP_OK) {
        // Success - restart
        esp_restart();
    } else {
        // Failure - indicate error
        indicate_error(ERR_OTA_FAIL);
    }
}
```

## 11. التشخيص والصيانة

### 11.1 سجلات التشخيص

```c
// Diagnostic Information Structure
typedef struct {
    uint32_t boot_count;
    uint32_t crash_count;
    uint32_t wifi_reconnects;
    uint32_t audio_errors;
    uint32_t ws_disconnects;
    float avg_latency_ms;
    uint32_t total_audio_minutes;
    char last_error[128];
} diagnostics_t;

void log_diagnostics(diagnostics_t *diag) {
    ESP_LOGI(TAG, "=== Diagnostics ===");
    ESP_LOGI(TAG, "Boots: %d, Crashes: %d", 
             diag->boot_count, diag->crash_count);
    ESP_LOGI(TAG, "WiFi Reconnects: %d", diag->wifi_reconnects);
    ESP_LOGI(TAG, "Audio Errors: %d", diag->audio_errors);
    ESP_LOGI(TAG, "Avg Latency: %.2fms", diag->avg_latency_ms);
}
```

### 11.2 أوامر التشخيص عبر UART

| الأمر | الوصف |
|------|-------|
| `status` | عرض الحالة الحالية |
| `wifi` | معلومات WiFi |
| `audio test` | اختبار الصوت |
| `reset` | إعادة تشغيل |
| `factory` | إعادة ضبط المصنع |
| `diag` | تقرير تشخيصي كامل |

## 12. المتطلبات والاعتماديات

### 12.1 مكتبات ESP-IDF المطلوبة

```yaml
dependencies:
  esp-idf: ">=4.4.0"
  components:
    - esp_websocket_client
    - nvs_flash
    - esp_wifi
    - esp_http_client
    - esp_https_ota
    - bluetooth
    - driver/i2s
    - driver/gpio
    - cJSON
```

### 12.2 الأجهزة الخارجية

| المكون | الموديل | الواجهة |
|--------|---------|----------|
| Microphone | INMP441 | I2S |
| Amplifier | MAX98357A | I2S |
| LED | WS2812B | GPIO |
| Battery Monitor | MAX17048 | I2C |

## 13. ملاحظات التنفيذ الحرجة

### ⚠️ نقاط حرجة يجب مراعاتها

1. **SSL/TLS**: حالياً معطل (`ssl_enabled=false`) للعمل مع Render.com
2. **Buffer Management**: استخدام Ring Buffers لتجنب فقدان الصوت
3. **Watchdog Timer**: تفعيل WDT لإعادة التشغيل التلقائي عند التعليق
4. **Memory Fragmentation**: استخدام static allocation للـ buffers الكبيرة
5. **WiFi Roaming**: دعم تبديل AP تلقائياً عند ضعف الإشارة

### 📊 مقاييس الأداء المستهدفة

| المقياس | الهدف | الحد الأقصى المقبول |
|---------|-------|-------------------|
| Audio Latency | <50ms | 100ms |
| WiFi Reconnect | <3s | 10s |
| JWT Refresh | <500ms | 2s |
| Boot Time | <5s | 10s |
| Memory Usage | <60% | 80% |

## 14. API Contracts - عقود التطبيق الملزِمة

### 14.1 REST API Endpoints

#### POST /pair/init
**الوصف**: إصدار رمز إقران جديد مع مفتاح PoP

**Request Schema**:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["parent_id", "child"],
  "properties": {
    "parent_id": { "type": "string", "format": "uuid" },
    "child": {
      "type": "object",
      "required": ["name", "age"],
      "properties": {
        "name": { "type": "string", "minLength": 1, "maxLength": 64 },
        "age": { "type": "integer", "minimum": 3, "maximum": 13 }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

**Response Schema (200)**:
```json
{
  "type": "object",
  "required": ["pairing_code", "pop_key", "child_id", "expires_in_sec"],
  "properties": {
    "pairing_code": { "type": "string", "pattern": "^[A-Z0-9-]{6,10}$" },
    "pop_key": { "type": "string", "contentEncoding": "base64" },
    "child_id": { "type": "string", "format": "uuid" },
    "expires_in_sec": { "type": "integer", "const": 600 }
  }
}
```

**Error Responses**:
- `400`: `{"error": "invalid_child" | "limit_reached"}`
- `401`: `{"error": "unauthorized"}`
- `429`: `{"error": "rate_limited", "retry_after_sec": 30}`

#### POST /device/session
**الوصف**: إصدار JWT للجهاز بعد التحقق من رمز الإقران

**Request Schema**:
```json
{
  "type": "object",
  "required": ["pairing_code", "nonce"],
  "properties": {
    "pairing_code": { "type": "string", "pattern": "^[A-Z0-9-]{6,10}$" },
    "device_pub": { "type": "string" },
    "nonce": { "type": "string", "minLength": 8, "maxLength": 64 }
  }
}
```

**Response Schema (200)**:
```json
{
  "type": "object",
  "required": ["device_id", "device_session_jwt", "child_id", "expires_in_sec"],
  "properties": {
    "device_id": { "type": "string" },
    "device_session_jwt": { "type": "string" },
    "child_id": { "type": "string", "format": "uuid" },
    "expires_in_sec": { "type": "integer", "const": 300 }
  }
}
```

### 14.2 WebSocket Contracts

#### WS /esp32/connect?device_id=...&child_id=...&auth=<jwt>
**الوصف**: اتصال الجهاز للمحادثات الصوتية

**الإطارات**:
- **Binary**: PCM 16kHz mono s16le (4096B chunks)
- **Text (JSON)**: رسائل التحكم والسياسات

**رسائل التحكم**:
```json
// Welcome (Server → ESP32)
{ "type": "welcome", "audio": { "sample_rate": 16000, "channels": 1, "format": "pcm_s16le" } }

// Policy (Server → ESP32)
{
  "type": "policy",
  "child_id": "uuid",
  "age": 7,
  "filters": {
    "content": "strict",
    "blocked_topics": ["violence", "personal_data"]
  }
}

// Auth Refresh (ESP32 → Server)
{ "type": "auth/refresh", "proof": "nonce-or-jti-tail" }

// Auth Response (Server → ESP32)
{ "type": "auth/ok", "exp_in_sec": 300 }

// Alert (Server → ESP32)
{
  "type": "alert",
  "severity": "high",
  "code": "pii_detected",
  "message": "Sensitive info detected"
}
```

#### WS /parent/notify?parent_id=...&child_id=...&auth=<parent_jwt>
**الوصف**: تنبيهات للوالدين (JSON فقط، لا صوت)

**أمثلة الرسائل**:
```json
// Child Status
{ "type": "child_status", "child_id": "uuid", "online": true, "device_id": "..." }

// Security Alert
{
  "type": "security_alert",
  "child_id": "uuid",
  "severity": "medium",
  "code": "pii_detected",
  "message": "Child mentioned phone number"
}

// Conversation Event
{ "type": "conversation_event", "child_id": "uuid", "event": "started", "ts": 1723200000 }
```

## 15. Redis Keys & Rate Limits

### 15.1 مفاتيح Redis والانتهاء

```bash
# Pairing Keys
pair:{pairing_code} -> {
  "child_id": "uuid",
  "pop_key": "base64",
  "created_at": 1723200000,
  "attempts": 0
}
TTL: 600 ثانية

# Session Keys
sess:{device_id}:{child_id} -> {
  "status": "connected",
  "last_seen": 1723200000,
  "jwt_exp": 1723200300
}
TTL: 600 ثانية (يُحدّث عند النشاط)

# Rate Limiting Keys
rate:{device_id} -> counters/windows
TTL: sliding windows (10s, 60s)
```

### 15.2 حدود المعدل (Rate Limits)

| النوع | الحد | النافذة | الإجراء عند التجاوز |
|------|-----|---------|--------------------|
| REST API | 30 طلب | 60 ثانية | HTTP 429 |
| WebSocket | 50 رسالة | 10 ثوانٍ | `rate_limited` + إسقاط 3s |
| BLE Pairing | 3 محاولات | 600 ثانية | رفض الطلب |
| JWT Refresh | 5 طلبات | 60 ثانية | فصل الاتصال |

## 16. Failure Matrix - مصفوفة الفشل

### 16.1 رموز إنهاء WebSocket

| الكود | السبب | إجراء الجهاز |
|------|-------|-------------|
| 4400 | `device_id` غير متطابق مع JWT | إعادة طلب JWT جديد |
| 4401 | JWT مفقود أو غير صحيح | إعادة طلب JWT جديد |
| 4403 | JWT منتهي الصلاحية + لا refresh | إعادة الإقران الكامل |
| 4429 | تجاوز Rate Limit | انتظار + إعادة المحاولة |
| 1011 | خطأ خادم داخلي | إعادة الاتصال خلال 5s |

### 16.2 رسائل الخطأ (JSON)

| النوع | المحتوى | إجراء الجهاز |
|------|---------|-------------|
| `rate_limited` | `{"type": "rate_limited", "window_sec": 10}` | توقف 3 ثوانٍ |
| `malformed_frame` | `{"type": "error", "code": "malformed_frame"}` | تدقيق تنسيق البيانات |
| `policy_violation` | `{"type": "error", "code": "policy_violation"}` | إيقاف الإرسال مؤقت |
| `auth_error` | `{"type": "auth/error", "reason": "expired"}` | طلب JWT جديد |

### 16.3 استراتيجية إعادة الاتصال

```c
// Reconnection Backoff Strategy
typedef struct {
    uint8_t attempt;      // Current attempt (0-5)
    uint32_t delay_ms;    // Current delay
    uint32_t max_delay;   // Max delay (30s)
} reconnect_state_t;

uint32_t calculate_backoff_delay(uint8_t attempt) {
    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s
    uint32_t delay = (1 << attempt) * 1000;  // 2^attempt seconds
    return (delay > 30000) ? 30000 : delay;  // Cap at 30s
}
```

## 17. TLS & Environment Variables

### 17.1 حالة TLS الحالية والمستقبلية

**الوضع الحالي** (Render.com):
```c
// NVS Configuration
bool ssl_enabled = false;  // Must be false for Render
char server_host[] = "your-app.onrender.com";
uint16_t server_port = 8000;

// WebSocket URL
ws://your-app.onrender.com:8000/esp32/connect
```

**الوضع المستقبلي** (Production TLS):
```c
// NVS Configuration  
bool ssl_enabled = true;
char server_host[] = "api.ai-teddy.com";
uint16_t server_port = 443;

// WebSocket URL
wss://api.ai-teddy.com/esp32/connect
```

### 17.2 متغيرات البيئة الحرجة

**Server Environment Variables**:
```bash
# JWT Security
DEVICE_JWT_SECRET="your-256-bit-secret-key"
PARENT_JWT_SECRET="your-256-bit-secret-key"

# Database
REDIS_URL="redis://localhost:6379"
DATABASE_URL="postgresql://user:pass@host:5432/db"

# Audio Services
OPENAI_API_KEY="sk-..."
ELEVENLABS_API_KEY="..."
VOICE_ID="21m00Tcm4TlvDq8ikWAM"  # Rachel voice
WHISPER_LANGUAGE="ar"  # Arabic

# Security
ALLOWED_ORIGINS="https://app.ai-teddy.com,https://admin.ai-teddy.com"
RATE_LIMIT_REDIS_URL="redis://localhost:6379/1"

# Deployment
PORT="8000"
SSL_ENABLED="false"  # Set to "true" for production
```

**ESP32 NVS Variables**:
```c
// Critical NVS Keys
char device_jwt_secret[64];    // Sync with server
char server_host[128];         // Runtime configurable
uint16_t server_port;          // 8000 (dev) or 443 (prod)
bool ssl_enabled;              // false (dev) or true (prod)
char ca_cert_pem[2048];        // Root CA for TLS
```

## 18. BLE Security - أمان البلوتوث

### 18.1 تشفير البيانات (BLE Payload Encryption)

**الخوارزمية**: AES-256-GCM
**طول المفتاح**: 256-bit (32 bytes)
**Nonce**: 96-bit (12 bytes) - يُولّد عشوائياً

```c
// BLE Encryption Implementation
typedef struct {
    uint8_t key[32];        // 256-bit PoP key from /pair/init
    uint8_t nonce[12];      // 96-bit random nonce
    uint8_t tag[16];        // 128-bit authentication tag
} ble_encryption_t;

// Encryption Process
int encrypt_ble_payload(const char* plaintext, 
                       const uint8_t* pop_key,
                       uint8_t* ciphertext, 
                       size_t* ciphertext_len) {
    
    // Generate random nonce
    esp_fill_random(nonce, 12);
    
    // AES-GCM encryption
    mbedtls_gcm_context ctx;
    mbedtls_gcm_init(&ctx);
    mbedtls_gcm_setkey(&ctx, MBEDTLS_CIPHER_ID_AES, pop_key, 256);
    
    // Encrypt and authenticate
    int ret = mbedtls_gcm_crypt_and_tag(&ctx,
                                       MBEDTLS_GCM_ENCRYPT,
                                       strlen(plaintext),
                                       nonce, 12,           // nonce
                                       NULL, 0,             // additional data
                                       (uint8_t*)plaintext, // input
                                       ciphertext,          // output
                                       16, tag);            // tag
    
    mbedtls_gcm_free(&ctx);
    return ret;
}
```

### 18.2 BLE Provisioning Packet Format

```c
// BLE Packet Structure
typedef struct __attribute__((packed)) {
    uint8_t nonce[12];      // Random nonce
    uint8_t tag[16];        // Authentication tag
    uint8_t ciphertext[];   // Encrypted JSON payload
} ble_packet_t;

// JSON Payload (before encryption)
{
  "ssid": "HomeWiFi",
  "password": "wifi-password",
  "child_id": "550e8400-e29b-41d4-a716-446655440000",
  "pairing_code": "A1-B2-C3"
}
```

### 18.3 BLE Service Characteristics

| UUID | النوع | الحجم الأقصى | الوصف |
|------|------|-------------|-------|
| `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` | Service | - | Nordic UART Service |
| `6E400002-B5A3-F393-E0A9-E50E24DCCA9E` | Write | 512 bytes | Encrypted provisioning data |
| `6E400003-B5A3-F393-E0A9-E50E24DCCA9E` | Notify | 64 bytes | Status responses |

**MTU Requirements**: 247 bytes minimum (لتمرير 512 bytes في جلسة واحدة)

## 19. خريطة الطريق المستقبلية

```mermaid
timeline
    title ESP32 Development Roadmap
    
    Q1 2024 : Basic Audio Streaming
            : BLE Provisioning
            : JWT Authentication
    
    Q2 2024 : Voice Activity Detection
            : Noise Cancellation
            : OTA Updates
    
    Q3 2024 : TLS/SSL Support
            : Audio Compression (Opus)
            : Advanced Power Management
    
    Q4 2024 : Matter/Thread Support
            : Edge AI Processing
            : Multi-Child Support
```