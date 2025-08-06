# AI Teddy Bear WebSocket API Guide

## 🔄 Real-time Communication

The AI Teddy Bear platform provides WebSocket connections for real-time interaction, safety monitoring, and live conversation streaming.

## 🌐 Connection Endpoints

### Primary Endpoints

- **Conversations**: `wss://api.aiteddybear.com/v1/ws/conversations`
- **Safety Monitor**: `wss://api.aiteddybear.com/v1/ws/safety`
- **Parent Dashboard**: `wss://api.aiteddybear.com/v1/ws/parent`
- **System Events**: `wss://api.aiteddybear.com/v1/ws/events`

### Sandbox Endpoints

- **Base URL**: `wss://sandbox.aiteddybear.com/v1/ws/`

## 🔐 Authentication

### WebSocket Authentication

```javascript
const ws = new WebSocket('wss://api.aiteddybear.com/v1/ws/conversations', [], {
    headers: {
        'Authorization': 'Bearer your-jwt-token',
        'X-Child-ID': 'child-uuid-here',
        'X-API-Version': '1.0'
    }
});
```

### Token Refresh

```javascript
// Handle token expiration
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'auth_expired') {
        // Refresh token and reconnect
        refreshToken().then(newToken => {
            ws.close();
            connectWithNewToken(newToken);
        });
    }
};
```

## 💬 Conversation WebSocket

### Connection Flow

```javascript
class ConversationWebSocket {
    constructor(token, childId) {
        this.token = token;
        this.childId = childId;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }
    
    connect() {
        const url = `wss://api.aiteddybear.com/v1/ws/conversations`;
        
        this.ws = new WebSocket(url, [], {
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'X-Child-ID': this.childId
            }
        });
        
        this.ws.onopen = this.onOpen.bind(this);
        this.ws.onmessage = this.onMessage.bind(this);
        this.ws.onclose = this.onClose.bind(this);
        this.ws.onerror = this.onError.bind(this);
    }
    
    onOpen() {
        console.log('Connected to AI Teddy Bear');
        this.reconnectAttempts = 0;
        
        // Send initial handshake
        this.send({
            type: 'handshake',
            child_id: this.childId,
            preferences: {
                voice_enabled: true,
                response_format: 'text_and_audio'
            }
        });
    }
    
    onMessage(event) {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
            case 'handshake_ack':
                this.handleHandshakeAck(data);
                break;
            case 'message_response':
                this.handleMessageResponse(data);
                break;
            case 'typing_indicator':
                this.handleTypingIndicator(data);
                break;
            case 'safety_warning':
                this.handleSafetyWarning(data);
                break;
            case 'session_ended':
                this.handleSessionEnded(data);
                break;
        }
    }
    
    sendMessage(content, options = {}) {
        const message = {
            type: 'user_message',
            content: content,
            timestamp: new Date().toISOString(),
            message_id: this.generateMessageId(),
            options: {
                voice_enabled: options.voiceEnabled || false,
                emotion_detection: options.emotionDetection || true,
                safety_check: options.safetyCheck !== false
            }
        };
        
        this.send(message);
    }
    
    send(data) {
        if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket not connected');
        }
    }
}
```

### Message Types

#### User Message

```json
{
    "type": "user_message",
    "content": "Hi Teddy! Tell me a story about dinosaurs",
    "timestamp": "2025-07-27T10:30:00Z",
    "message_id": "msg_123456",
    "options": {
        "voice_enabled": true,
        "emotion_detection": true,
        "safety_check": true
    }
}
```

#### AI Response

```json
{
    "type": "message_response",
    "content": "Once upon a time, there was a friendly dinosaur named Rex...",
    "message_id": "msg_123456",
    "response_id": "resp_789012",
    "timestamp": "2025-07-27T10:30:15Z",
    "metadata": {
        "safety_score": 1.0,
        "emotion": "excited",
        "audio_url": "https://cdn.aiteddybear.com/audio/resp_789012.mp3",
        "audio_duration": 45.2,
        "response_time_ms": 2300
    }
}
```

#### Typing Indicator

```json
{
    "type": "typing_indicator",
    "status": "typing",
    "estimated_response_time": 3000
}
```

#### Safety Warning

```json
{
    "type": "safety_warning",
    "severity": "medium",
    "reason": "Detected request for personal information",
    "recommendation": "Redirect conversation to safe topics",
    "auto_handled": true
}
```

## 🛡️ Safety Monitor WebSocket

### Real-time Safety Monitoring

```javascript
class SafetyMonitor {
    constructor(token, childId) {
        this.token = token;
        this.childId = childId;
        this.ws = null;
    }
    
    connect() {
        const url = `wss://api.aiteddybear.com/v1/ws/safety`;
        
        this.ws = new WebSocket(url, [], {
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'X-Child-ID': this.childId
            }
        });
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleSafetyEvent(data);
        };
    }
    
    handleSafetyEvent(event) {
        switch (event.type) {
            case 'content_violation':
                this.handleContentViolation(event);
                break;
            case 'behavior_concern':
                this.handleBehaviorConcern(event);
                break;
            case 'usage_limit':
                this.handleUsageLimit(event);
                break;
            case 'parent_notification':
                this.handleParentNotification(event);
                break;
        }
    }
    
    handleContentViolation(event) {
        // Immediate action required
        if (event.severity === 'high') {
            this.terminateSession();
            this.notifyParents(event);
        }
    }
}
```

### Safety Event Types

#### Content Violation

```json
{
    "type": "content_violation",
    "severity": "high",
    "violation_type": "inappropriate_content_request",
    "content_hash": "sha256:abc123...",
    "timestamp": "2025-07-27T10:35:00Z",
    "action_taken": "conversation_terminated",
    "parent_notified": true,
    "correlation_id": "safety_evt_456789"
}
```

#### Behavior Concern

```json
{
    "type": "behavior_concern",
    "concern_type": "excessive_usage",
    "details": {
        "session_duration": 3600,
        "daily_usage": 7200,
        "recommended_break": 900
    },
    "recommendation": "Suggest break and outdoor activity",
    "timestamp": "2025-07-27T11:00:00Z"
}
```

## 👨‍👩‍👧 Parent Dashboard WebSocket

### Real-time Parent Monitoring

```javascript
class ParentDashboard {
    constructor(token) {
        this.token = token;
        this.ws = null;
        this.childrenData = new Map();
    }
    
    connect() {
        const url = `wss://api.aiteddybear.com/v1/ws/parent`;
        
        this.ws = new WebSocket(url, [], {
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'X-Role': 'parent'
            }
        });
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleParentUpdate(data);
        };
    }
    
    handleParentUpdate(update) {
        switch (update.type) {
            case 'child_activity':
                this.updateChildActivity(update);
                break;
            case 'safety_alert':
                this.handleSafetyAlert(update);
                break;
            case 'usage_summary':
                this.updateUsageSummary(update);
                break;
            case 'consent_request':
                this.handleConsentRequest(update);
                break;
        }
    }
    
    // Subscribe to specific child updates
    subscribeToChild(childId) {
        this.send({
            type: 'subscribe',
            child_id: childId,
            events: ['activity', 'safety', 'usage']
        });
    }
    
    // Parent controls
    pauseChildSession(childId) {
        this.send({
            type: 'parent_control',
            action: 'pause_session',
            child_id: childId,
            reason: 'parent_request'
        });
    }
    
    setUsageLimit(childId, limitMinutes) {
        this.send({
            type: 'parent_control',
            action: 'set_usage_limit',
            child_id: childId,
            limit_minutes: limitMinutes
        });
    }
}
```

## 🎵 Audio Streaming

### Real-time Audio

```javascript
class AudioStreaming {
    constructor(conversationWs) {
        this.conversationWs = conversationWs;
        this.audioContext = new AudioContext();
        this.audioQueue = [];
    }
    
    handleAudioStream(data) {
        if (data.type === 'audio_chunk') {
            this.playAudioChunk(data.chunk);
        } else if (data.type === 'audio_complete') {
            this.finalizeAudio();
        }
    }
    
    async playAudioChunk(base64Chunk) {
        const audioData = this.base64ToArrayBuffer(base64Chunk);
        const audioBuffer = await this.audioContext.decodeAudioData(audioData);
        
        const source = this.audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.audioContext.destination);
        source.start();
    }
    
    // Request audio streaming
    enableAudioStreaming() {
        this.conversationWs.send({
            type: 'enable_audio_streaming',
            format: 'mp3',
            sample_rate: 44100,
            chunk_size: 1024
        });
    }
}
```

## 🔄 Connection Management

### Reconnection Logic

```javascript
class WebSocketManager {
    constructor(url, token, options = {}) {
        this.url = url;
        this.token = token;
        this.options = {
            maxReconnectAttempts: 10,
            reconnectInterval: 1000,
            maxReconnectInterval: 30000,
            reconnectDecay: 1.5,
            ...options
        };
        
        this.reconnectAttempts = 0;
        this.ws = null;
        this.shouldReconnect = true;
    }
    
    connect() {
        try {
            this.ws = new WebSocket(this.url, [], {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
            };
            
            this.ws.onclose = (event) => {
                if (this.shouldReconnect && !event.wasClean) {
                    this.scheduleReconnect();
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.scheduleReconnect();
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }
        
        const interval = Math.min(
            this.options.reconnectInterval * Math.pow(this.options.reconnectDecay, this.reconnectAttempts),
            this.options.maxReconnectInterval
        );
        
        console.log(`Reconnecting in ${interval}ms (attempt ${this.reconnectAttempts + 1})`);
        
        setTimeout(() => {
            this.reconnectAttempts++;
            this.connect();
        }, interval);
    }
    
    disconnect() {
        this.shouldReconnect = false;
        if (this.ws) {
            this.ws.close();
        }
    }
}
```

## 📊 Performance Monitoring

### Connection Metrics

```javascript
class WebSocketMetrics {
    constructor(ws) {
        this.ws = ws;
        this.metrics = {
            messagesReceived: 0,
            messagesSent: 0,
            bytesReceived: 0,
            bytesSent: 0,
            averageLatency: 0,
            connectionUptime: 0,
            reconnections: 0
        };
        
        this.startTime = Date.now();
        this.latencyMeasurements = [];
    }
    
    trackMessage(type, size, latency) {
        if (type === 'sent') {
            this.metrics.messagesSent++;
            this.metrics.bytesSent += size;
        } else {
            this.metrics.messagesReceived++;
            this.metrics.bytesReceived += size;
            
            if (latency) {
                this.latencyMeasurements.push(latency);
                this.updateAverageLatency();
            }
        }
    }
    
    updateAverageLatency() {
        if (this.latencyMeasurements.length > 0) {
            const sum = this.latencyMeasurements.reduce((a, b) => a + b, 0);
            this.metrics.averageLatency = sum / this.latencyMeasurements.length;
        }
    }
    
    getMetrics() {
        this.metrics.connectionUptime = Date.now() - this.startTime;
        return { ...this.metrics };
    }
}
```

## 🚨 Error Handling

### WebSocket Error Types

```javascript
class WebSocketErrorHandler {
    constructor(ws) {
        this.ws = ws;
        this.errorHandlers = new Map();
    }
    
    handleError(error) {
        switch (error.type) {
            case 'connection_failed':
                this.handleConnectionError(error);
                break;
            case 'authentication_failed':
                this.handleAuthError(error);
                break;
            case 'rate_limit_exceeded':
                this.handleRateLimitError(error);
                break;
            case 'safety_violation':
                this.handleSafetyError(error);
                break;
            case 'service_unavailable':
                this.handleServiceError(error);
                break;
            default:
                this.handleGenericError(error);
        }
    }
    
    handleConnectionError(error) {
        console.warn('Connection failed, attempting reconnect...');
        // Implement exponential backoff
    }
    
    handleAuthError(error) {
        console.error('Authentication failed:', error.message);
        // Redirect to login or refresh token
    }
    
    handleRateLimitError(error) {
        console.warn(`Rate limited. Retry after ${error.retryAfter}s`);
        // Implement rate limit handling
    }
    
    handleSafetyError(error) {
        console.error('Safety violation detected:', error.details);
        // Handle safety violations
        this.notifyParent(error);
    }
}
```

## 🧪 Testing WebSockets

### Mock WebSocket for Testing

```javascript
class MockWebSocket {
    constructor(url, protocols, options) {
        this.url = url;
        this.readyState = WebSocket.CONNECTING;
        this.onopen = null;
        this.onmessage = null;
        this.onclose = null;
        this.onerror = null;
        
        // Simulate connection
        setTimeout(() => {
            this.readyState = WebSocket.OPEN;
            if (this.onopen) this.onopen();
        }, 100);
    }
    
    send(data) {
        // Mock server responses
        const message = JSON.parse(data);
        
        if (message.type === 'user_message') {
            setTimeout(() => {
                this.simulateResponse(message);
            }, 1000);
        }
    }
    
    simulateResponse(originalMessage) {
        const response = {
            type: 'message_response',
            content: 'This is a mock response from Teddy!',
            message_id: originalMessage.message_id,
            response_id: 'mock_resp_123',
            timestamp: new Date().toISOString(),
            metadata: {
                safety_score: 1.0,
                emotion: 'happy',
                response_time_ms: 1000
            }
        };
        
        if (this.onmessage) {
            this.onmessage({ data: JSON.stringify(response) });
        }
    }
    
    close() {
        this.readyState = WebSocket.CLOSED;
        if (this.onclose) this.onclose();
    }
}

// Use in tests
global.WebSocket = MockWebSocket;
```

## 📋 Best Practices

### 1. Connection Management
- Always implement reconnection logic
- Handle network interruptions gracefully
- Use exponential backoff for reconnections

### 2. Error Handling
- Implement comprehensive error handling
- Log errors with correlation IDs
- Provide user-friendly error messages

### 3. Performance
- Monitor connection metrics
- Implement message queuing for reliability
- Use compression for large messages

### 4. Security
- Validate all incoming messages
- Implement rate limiting on client side
- Use secure WebSocket connections (WSS)

### 5. Child Safety
- Monitor all real-time communications
- Implement immediate safety violation handling
- Provide parent visibility into all interactions
