/**
 * WebSocket Service - خدمة الاتصال المباشر مع السيرفر
 * 
 * Features:
 * - Real-time bidirectional communication
 * - Auto-reconnection with exponential backoff
 * - Connection state management
 * - Event-driven architecture
 * - Heartbeat mechanism
 * - Message queuing during disconnection
 * 
 * @version 1.0.0
 * @since 2025-08-04
 */

import { EventEmitter } from 'events';
import { config } from '../config';
import { SecureStorage } from './SecureStorageService';

export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
  id?: string;
}

export interface ConnectionState {
  connected: boolean;
  connecting: boolean;
  reconnecting: boolean;
  lastConnected?: string;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
}

export class WebSocketService extends EventEmitter {
  private static instance: WebSocketService;
  private ws: WebSocket | null = null;
  private connectionState: ConnectionState = {
    connected: false,
    connecting: false,
    reconnecting: false,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5
  };
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private messageQueue: WebSocketMessage[] = [];
  private lastHeartbeat: number = 0;
  private readonly HEARTBEAT_INTERVAL = 30000; // 30 seconds
  private readonly RECONNECT_DELAY_BASE = 1000; // 1 second base delay

  private constructor() {
    super();
  }

  public static getInstance(): WebSocketService {
    if (!WebSocketService.instance) {
      WebSocketService.instance = new WebSocketService();
    }
    return WebSocketService.instance;
  }

  /**
   * الاتصال بسيرفر WebSocket
   */
  public async connect(): Promise<void> {
    if (this.connectionState.connected || this.connectionState.connecting) {
      console.log('🔄 WebSocket already connected or connecting');
      return;
    }

    try {
      this.connectionState.connecting = true;
      this.emit('connecting');

      console.log('🔗 Connecting to WebSocket server...');

      // الحصول على token المصادقة من التخزين الآمن
      const authToken = await SecureStorage.getToken();
      if (!authToken) {
        throw new Error('No authentication token found');
      }

      // بناء URL للاتصال
      const wsUrl = this.buildWebSocketUrl(authToken);
      
      // إنشاء الاتصال
      this.ws = new WebSocket(wsUrl);
      
      // تسجيل معالجات الأحداث
      this.setupEventHandlers();

      // انتظار الاتصال أو الفشل
      await this.waitForConnection();

      console.log('✅ WebSocket connected successfully');

    } catch (error) {
      console.error('❌ WebSocket connection failed:', error);
      this.connectionState.connecting = false;
      this.emit('connection_error', error);
      
      // محاولة إعادة الاتصال
      this.scheduleReconnect();
      throw error;
    }
  }

  /**
   * قطع الاتصال
   */
  public async disconnect(): Promise<void> {
    console.log('🔌 Disconnecting WebSocket...');

    this.clearReconnectTimeout();
    this.stopHeartbeat();

    if (this.ws) {
      this.ws.close(1000, 'Normal closure');
      this.ws = null;
    }

    this.updateConnectionState({
      connected: false,
      connecting: false,
      reconnecting: false
    });

    this.emit('disconnected');
    console.log('✅ WebSocket disconnected');
  }

  /**
   * إرسال رسالة
   */
  public send(type: string, data: any): void {
    const message: WebSocketMessage = {
      type,
      data,
      timestamp: new Date().toISOString(),
      id: this.generateMessageId()
    };

    if (this.connectionState.connected && this.ws) {
      try {
        this.ws.send(JSON.stringify(message));
        console.log('📤 Message sent:', type);
      } catch (error) {
        console.error('❌ Error sending message:', error);
        this.queueMessage(message);
      }
    } else {
      console.log('📬 Queuing message (not connected):', type);
      this.queueMessage(message);
    }
  }

  /**
   * التحقق من حالة الاتصال
   */
  public isConnected(): boolean {
    return this.connectionState.connected;
  }

  /**
   * الحصول على حالة الاتصال
   */
  public getConnectionState(): ConnectionState {
    return { ...this.connectionState };
  }

  /**
   * بناء URL للاتصال الآمن
   */
  private buildWebSocketUrl(authToken: string): string {
    const wsUrl = config.WS_BASE_URL;
    
    // Security check: Ensure WSS in production
    if (config.app.environment === 'production' && !wsUrl.startsWith('wss://')) {
      throw new Error('🚨 SECURITY: WebSocket must use WSS in production');
    }
    
    return `${wsUrl}/ws/alerts?token=${authToken}`;
  }

  /**
   * تسجيل معالجات أحداث WebSocket
   */
  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = this.handleOpen.bind(this);
    this.ws.onmessage = this.handleMessage.bind(this);
    this.ws.onclose = this.handleClose.bind(this);
    this.ws.onerror = this.handleError.bind(this);
  }

  /**
   * معالجة فتح الاتصال
   */
  private handleOpen(): void {
    console.log('🎉 WebSocket connection opened');

    this.updateConnectionState({
      connected: true,
      connecting: false,
      reconnecting: false,
      reconnectAttempts: 0,
      lastConnected: new Date().toISOString()
    });

    this.startHeartbeat();
    this.sendQueuedMessages();
    this.emit('connected');

    // إذا كان هذا إعادة اتصال
    if (this.connectionState.reconnectAttempts > 0) {
      this.emit('reconnected');
    }
  }

  /**
   * معالجة الرسائل الواردة
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      
      console.log('📥 WebSocket message received:', message.type);

      // تحديث وقت آخر heartbeat
      this.lastHeartbeat = Date.now();

      // معالجة أنواع الرسائل المختلفة
      switch (message.type) {
        case 'heartbeat':
          this.handleHeartbeat();
          break;
        case 'safety_alert':
          this.emit('safety_alert', message.data);
          break;
        case 'risk_assessment_update':
          this.emit('risk_assessment_update', message.data);
          break;
        case 'child_status_update':
          this.emit('child_status_update', message.data);
          break;
        case 'system_notification':
          this.emit('system_notification', message.data);
          break;
        default:
          console.log('📨 Unknown message type:', message.type);
          this.emit('message', message);
      }

    } catch (error) {
      console.error('❌ Error parsing WebSocket message:', error);
    }
  }

  /**
   * معالجة إغلاق الاتصال
   */
  private handleClose(event: CloseEvent): void {
    console.log('🔌 WebSocket connection closed:', event.code, event.reason);

    this.updateConnectionState({
      connected: false,
      connecting: false
    });

    this.stopHeartbeat();
    this.emit('disconnected', event);

    // إعادة الاتصال إذا لم يكن إغلاق طبيعي
    if (event.code !== 1000 && event.code !== 1001) {
      this.scheduleReconnect();
    }
  }

  /**
   * معالجة الأخطاء
   */
  private handleError(event: Event): void {
    console.error('❌ WebSocket error:', event);
    this.emit('error', event);

    // إذا كان متصل، جدول إعادة الاتصال
    if (this.connectionState.connected) {
      this.scheduleReconnect();
    }
  }

  /**
   * انتظار تأسيس الاتصال
   */
  private waitForConnection(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.ws) {
        reject(new Error('WebSocket not initialized'));
        return;
      }

      const timeout = setTimeout(() => {
        reject(new Error('WebSocket connection timeout'));
      }, 10000); // 10 seconds timeout

      const onOpen = () => {
        clearTimeout(timeout);
        resolve();
      };

      const onError = (error: Event) => {
        clearTimeout(timeout);
        reject(error);
      };

      this.ws.addEventListener('open', onOpen, { once: true });
      this.ws.addEventListener('error', onError, { once: true });
    });
  }

  /**
   * جدولة إعادة الاتصال
   */
  private scheduleReconnect(): void {
    if (this.connectionState.reconnectAttempts >= this.connectionState.maxReconnectAttempts) {
      console.log('❌ Max reconnection attempts reached');
      this.emit('max_reconnect_attempts_reached');
      return;
    }

    const delay = this.calculateReconnectDelay();
    
    console.log(`🔄 Scheduling reconnect in ${delay}ms (attempt ${this.connectionState.reconnectAttempts + 1})`);

    this.connectionState.reconnecting = true;
    this.connectionState.reconnectAttempts++;

    this.reconnectTimeout = setTimeout(() => {
      this.attemptReconnect();
    }, delay);

    this.emit('reconnecting', this.connectionState.reconnectAttempts);
  }

  /**
   * محاولة إعادة الاتصال
   */
  private async attemptReconnect(): Promise<void> {
    try {
      console.log(`🔄 Attempting to reconnect... (${this.connectionState.reconnectAttempts}/${this.connectionState.maxReconnectAttempts})`);
      
      await this.connect();
      
    } catch (error) {
      console.error('❌ Reconnection failed:', error);
      this.scheduleReconnect();
    }
  }

  /**
   * حساب تأخير إعادة الاتصال (Exponential Backoff)
   */
  private calculateReconnectDelay(): number {
    const attempt = this.connectionState.reconnectAttempts;
    const delay = Math.min(
      this.RECONNECT_DELAY_BASE * Math.pow(2, attempt),
      30000 // Max 30 seconds
    );
    
    // إضافة عشوائية لتجنب thundering herd
    return delay + Math.random() * 1000;
  }

  /**
   * بدء نبضات القلب
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatInterval = setInterval(() => {
      if (this.connectionState.connected) {
        this.send('heartbeat', { timestamp: Date.now() });
        
        // التحقق من انقطاع الاتصال
        if (Date.now() - this.lastHeartbeat > this.HEARTBEAT_INTERVAL * 2) {
          console.log('💔 Heartbeat timeout detected');
          this.handleHeartbeatTimeout();
        }
      }
    }, this.HEARTBEAT_INTERVAL);

    this.lastHeartbeat = Date.now();
  }

  /**
   * إيقاف نبضات القلب
   */
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /**
   * معالجة نبضة القلب
   */
  private handleHeartbeat(): void {
    // إرسال رد على نبضة القلب
    this.send('heartbeat_response', { timestamp: Date.now() });
  }

  /**
   * معالجة انقطاع نبضة القلب
   */
  private handleHeartbeatTimeout(): void {
    console.log('💔 Heartbeat timeout - reconnecting...');
    this.disconnect();
    this.scheduleReconnect();
  }

  /**
   * إضافة رسالة للقائمة
   */
  private queueMessage(message: WebSocketMessage): void {
    this.messageQueue.push(message);
    
    // الاحتفاظ بحد أقصى من الرسائل
    if (this.messageQueue.length > 100) {
      this.messageQueue.shift(); // إزالة الأقدم
    }
  }

  /**
   * إرسال الرسائل المؤجلة
   */
  private sendQueuedMessages(): void {
    console.log(`📬 Sending ${this.messageQueue.length} queued messages`);
    
    while (this.messageQueue.length > 0 && this.connectionState.connected) {
      const message = this.messageQueue.shift();
      if (message && this.ws) {
        try {
          this.ws.send(JSON.stringify(message));
        } catch (error) {
          console.error('❌ Error sending queued message:', error);
          // إعادة إضافة الرسالة للقائمة
          this.messageQueue.unshift(message);
          break;
        }
      }
    }
  }

  /**
   * تحديث حالة الاتصال
   */
  private updateConnectionState(updates: Partial<ConnectionState>): void {
    this.connectionState = { ...this.connectionState, ...updates };
    this.emit('connection_state_changed', this.connectionState);
  }

  /**
   * إلغاء timeout إعادة الاتصال
   */
  private clearReconnectTimeout(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  /**
   * توليد معرف رسالة فريد
   */
  private generateMessageId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * إحصائيات الاتصال
   */
  public getStats() {
    return {
      connection_state: this.connectionState,
      queued_messages: this.messageQueue.length,
      last_heartbeat: this.lastHeartbeat,
      heartbeat_active: this.heartbeatInterval !== null,
      reconnect_scheduled: this.reconnectTimeout !== null
    };
  }

  /**
   * تنظيف الموارد
   */
  public cleanup(): void {
    this.disconnect();
    this.clearReconnectTimeout();
    this.messageQueue = [];
    this.removeAllListeners();
    console.log('✅ WebSocketService cleanup completed');
  }
}

export default WebSocketService;
